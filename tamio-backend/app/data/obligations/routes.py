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
from app.schemas.reconciliation import (
    ReconciliationSuggestion,
    ReconciliationSuggestionList,
    ApproveReconciliationRequest,
    BulkReconciliationRequest,
    BulkReconciliationResult,
    RejectReconciliationRequest,
    RevertReconciliationRequest,
    ForecastImpactItem,
    ForecastImpactSummary,
    ReconciliationSettings,
    ReconciliationSettingsUpdate,
    ReconciliationQueueSummary,
)
from app.auth.dependencies import get_current_user

router = APIRouter()


# ============================================
# ObligationAgreement Endpoints (Layer 1)
# ============================================

@router.post("/obligations", response_model=ObligationAgreementResponse, status_code=status.HTTP_201_CREATED)
async def create_obligation_agreement(
    obligation: ObligationAgreementCreate,
    current_user: models.User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Create a new obligation agreement (Layer 1: WHY).

    This defines the structural reason for a committed cash-out.
    """
    # Create obligation agreement with authenticated user's ID
    obligation_data = obligation.model_dump()
    obligation_data["user_id"] = current_user.id
    db_obligation = models.ObligationAgreement(**obligation_data)

    db.add(db_obligation)
    await db.commit()
    await db.refresh(db_obligation)

    return db_obligation


@router.get("/obligations", response_model=List[ObligationAgreementResponse])
async def list_obligation_agreements(
    current_user: models.User = Depends(get_current_user),
    category: Optional[str] = None,
    obligation_type: Optional[str] = None,
    active_only: bool = True,
    db: AsyncSession = Depends(get_db)
):
    """
    List all obligation agreements for the authenticated user.

    Filters:
    - category: Filter by expense category (payroll, rent, etc.)
    - obligation_type: Filter by type (subscription, vendor_bill, etc.)
    - active_only: Only show active obligations (end_date is null or in future)
    """
    query = select(models.ObligationAgreement).where(
        models.ObligationAgreement.user_id == current_user.id
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
    current_user: models.User = Depends(get_current_user),
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

    # Verify ownership
    if obligation.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to access this obligation"
        )

    return obligation


@router.patch("/obligations/{obligation_id}", response_model=ObligationAgreementResponse)
async def update_obligation_agreement(
    obligation_id: str,
    updates: ObligationAgreementUpdate,
    current_user: models.User = Depends(get_current_user),
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

    # Verify ownership
    if obligation.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to modify this obligation"
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
    current_user: models.User = Depends(get_current_user),
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

    # Verify ownership
    if obligation.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to delete this obligation"
        )

    await db.delete(obligation)
    await db.commit()


# ============================================
# ObligationSchedule Endpoints (Layer 2)
# ============================================

@router.post("/schedules", response_model=ObligationScheduleResponse, status_code=status.HTTP_201_CREATED)
async def create_obligation_schedule(
    schedule: ObligationScheduleCreate,
    current_user: models.User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Create a new scheduled payment (Layer 2: WHEN).

    This defines when a payment is expected for an obligation.
    """
    # Verify obligation exists and belongs to current user
    obligation_query = select(models.ObligationAgreement).where(
        models.ObligationAgreement.id == schedule.obligation_id
    )
    result = await db.execute(obligation_query)
    obligation = result.scalar_one_or_none()

    if not obligation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Obligation {schedule.obligation_id} not found"
        )

    if obligation.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to create schedules for this obligation"
        )

    # Create schedule
    db_schedule = models.ObligationSchedule(**schedule.model_dump())

    db.add(db_schedule)
    await db.commit()
    await db.refresh(db_schedule)

    return db_schedule


@router.get("/schedules", response_model=List[ObligationScheduleResponse])
async def list_obligation_schedules(
    current_user: models.User = Depends(get_current_user),
    obligation_id: Optional[str] = None,
    from_date: Optional[date] = None,
    to_date: Optional[date] = None,
    schedule_status: Optional[str] = None,
    db: AsyncSession = Depends(get_db)
):
    """
    List scheduled payments for the authenticated user.

    Filters:
    - obligation_id: Get schedules for specific obligation
    - from_date / to_date: Filter by due date range
    - schedule_status: Filter by status (scheduled, due, paid, overdue, cancelled)
    """
    # Join with ObligationAgreement to filter by user
    query = select(models.ObligationSchedule).join(models.ObligationAgreement).where(
        models.ObligationAgreement.user_id == current_user.id
    )

    if obligation_id:
        query = query.where(models.ObligationSchedule.obligation_id == obligation_id)

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
    current_user: models.User = Depends(get_current_user),
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

    # Verify ownership via obligation
    obligation_query = select(models.ObligationAgreement).where(
        models.ObligationAgreement.id == schedule.obligation_id
    )
    obligation_result = await db.execute(obligation_query)
    obligation = obligation_result.scalar_one_or_none()

    if not obligation or obligation.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to access this schedule"
        )

    return schedule


@router.patch("/schedules/{schedule_id}", response_model=ObligationScheduleResponse)
async def update_obligation_schedule(
    schedule_id: str,
    updates: ObligationScheduleUpdate,
    current_user: models.User = Depends(get_current_user),
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

    # Verify ownership via obligation
    obligation_query = select(models.ObligationAgreement).where(
        models.ObligationAgreement.id == schedule.obligation_id
    )
    obligation_result = await db.execute(obligation_query)
    obligation = obligation_result.scalar_one_or_none()

    if not obligation or obligation.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to modify this schedule"
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
    current_user: models.User = Depends(get_current_user),
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

    # Verify ownership via obligation
    obligation_query = select(models.ObligationAgreement).where(
        models.ObligationAgreement.id == schedule.obligation_id
    )
    obligation_result = await db.execute(obligation_query)
    obligation = obligation_result.scalar_one_or_none()

    if not obligation or obligation.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to delete this schedule"
        )

    await db.delete(schedule)
    await db.commit()


# ============================================
# PaymentEvent Endpoints (Layer 3)
# ============================================

@router.post("/payments", response_model=PaymentEventResponse, status_code=status.HTTP_201_CREATED)
async def create_payment_event(
    payment: PaymentEventCreate,
    current_user: models.User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Record an actual payment (Layer 3: REALITY).

    This represents confirmed cash-out from a bank account.

    If schedule_id is provided, will automatically mark that schedule as "paid"
    and set is_reconciled to True.
    """
    # Create payment event with authenticated user's ID
    payment_data = payment.model_dump()
    payment_data["user_id"] = current_user.id
    db_payment = models.PaymentEvent(**payment_data)

    # If schedule_id provided, verify ownership and mark schedule as paid
    if payment.schedule_id:
        schedule_query = select(models.ObligationSchedule).where(
            models.ObligationSchedule.id == payment.schedule_id
        )
        result = await db.execute(schedule_query)
        schedule = result.scalar_one_or_none()

        if schedule:
            # Verify ownership via obligation
            obligation_query = select(models.ObligationAgreement).where(
                models.ObligationAgreement.id == schedule.obligation_id
            )
            obligation_result = await db.execute(obligation_query)
            obligation = obligation_result.scalar_one_or_none()

            if not obligation or obligation.user_id != current_user.id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Not authorized to link payment to this schedule"
                )

            schedule.status = "paid"
            db_payment.is_reconciled = True
            db_payment.reconciled_at = datetime.utcnow()

    db.add(db_payment)
    await db.commit()
    await db.refresh(db_payment)

    return db_payment


@router.get("/payments", response_model=List[PaymentEventResponse])
async def list_payment_events(
    current_user: models.User = Depends(get_current_user),
    obligation_id: Optional[str] = None,
    from_date: Optional[date] = None,
    to_date: Optional[date] = None,
    payment_status: Optional[str] = None,
    reconciled_only: bool = False,
    db: AsyncSession = Depends(get_db)
):
    """
    List actual payment events for the authenticated user.

    Filters:
    - obligation_id: Filter by specific obligation
    - from_date / to_date: Filter by payment date range
    - payment_status: Filter by status (pending, completed, failed, reversed)
    - reconciled_only: Only show reconciled payments
    """
    query = select(models.PaymentEvent).where(
        models.PaymentEvent.user_id == current_user.id
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
    current_user: models.User = Depends(get_current_user),
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

    # Verify ownership
    if payment.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to access this payment"
        )

    return payment


@router.patch("/payments/{payment_id}", response_model=PaymentEventResponse)
async def update_payment_event(
    payment_id: str,
    updates: PaymentEventUpdate,
    current_user: models.User = Depends(get_current_user),
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

    # Verify ownership
    if payment.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to modify this payment"
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
    current_user: models.User = Depends(get_current_user),
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

    # Verify ownership
    if payment.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to delete this payment"
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
    current_user: models.User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Link a payment event to a scheduled payment (reconciliation).

    This connects Layer 3 (REALITY) to Layer 2 (WHEN).
    """
    # Get payment and verify ownership
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

    if payment.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to modify this payment"
        )

    # Get schedule and verify ownership
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

    # Verify schedule ownership via obligation
    obligation_query = select(models.ObligationAgreement).where(
        models.ObligationAgreement.id == schedule.obligation_id
    )
    obligation_result = await db.execute(obligation_query)
    obligation = obligation_result.scalar_one_or_none()

    if not obligation or obligation.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to reconcile with this schedule"
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
    current_user: models.User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Get all payments that haven't been reconciled to a schedule.
    """
    query = select(models.PaymentEvent).where(
        and_(
            models.PaymentEvent.user_id == current_user.id,
            models.PaymentEvent.is_reconciled == False
        )
    ).order_by(models.PaymentEvent.payment_date.desc())

    result = await db.execute(query)
    payments = result.scalars().all()

    return payments


@router.get("/reconciliation/unpaid-schedules", response_model=List[ObligationScheduleResponse])
async def list_unpaid_schedules(
    current_user: models.User = Depends(get_current_user),
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
            models.ObligationAgreement.user_id == current_user.id,
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


# ============================================
# AI Reconciliation Endpoints
# ============================================

def _calculate_match_confidence(payment: models.PaymentEvent, schedule: models.ObligationSchedule, obligation: models.ObligationAgreement) -> tuple[float, str]:
    """
    Calculate confidence score for a potential payment-schedule match.
    Returns (confidence_score, reasoning).
    """
    confidence = 0.0
    reasons = []

    # Amount matching (up to 40%)
    if payment.amount and schedule.estimated_amount:
        amount_diff = abs(float(payment.amount) - float(schedule.estimated_amount))
        amount_ratio = amount_diff / float(schedule.estimated_amount) if schedule.estimated_amount else 1.0

        if amount_ratio == 0:
            confidence += 0.40
            reasons.append("Exact amount match")
        elif amount_ratio < 0.05:
            confidence += 0.35
            reasons.append("Amount within 5%")
        elif amount_ratio < 0.10:
            confidence += 0.25
            reasons.append("Amount within 10%")
        elif amount_ratio < 0.20:
            confidence += 0.15
            reasons.append("Amount within 20%")

    # Date proximity (up to 30%)
    if payment.payment_date and schedule.due_date:
        date_diff = abs((payment.payment_date - schedule.due_date).days)

        if date_diff == 0:
            confidence += 0.30
            reasons.append("Paid on due date")
        elif date_diff <= 3:
            confidence += 0.25
            reasons.append(f"Paid within 3 days of due date")
        elif date_diff <= 7:
            confidence += 0.20
            reasons.append(f"Paid within a week of due date")
        elif date_diff <= 14:
            confidence += 0.10
            reasons.append(f"Paid within 2 weeks of due date")

    # Vendor name matching (up to 20%)
    if payment.vendor_name and obligation.vendor_name:
        payment_vendor = payment.vendor_name.lower().strip()
        obligation_vendor = obligation.vendor_name.lower().strip()

        if payment_vendor == obligation_vendor:
            confidence += 0.20
            reasons.append("Exact vendor name match")
        elif payment_vendor in obligation_vendor or obligation_vendor in payment_vendor:
            confidence += 0.15
            reasons.append("Partial vendor name match")

    # Source confidence boost (up to 10%)
    if schedule.estimate_source == "xero_invoice":
        confidence += 0.10
        reasons.append("Linked to Xero invoice")
    elif schedule.estimate_source == "fixed_agreement":
        confidence += 0.08
        reasons.append("Based on fixed agreement")

    reasoning = ". ".join(reasons) if reasons else "Low confidence match based on available data"

    return min(confidence, 1.0), reasoning


@router.get("/reconciliation/suggestions", response_model=ReconciliationSuggestionList)
async def get_reconciliation_suggestions(
    current_user: models.User = Depends(get_current_user),
    include_auto_approved: bool = False,
    db: AsyncSession = Depends(get_db)
):
    """
    Get AI-generated suggestions for matching unreconciled payments to schedules.

    The AI analyzes:
    - Amount similarity
    - Date proximity (payment date vs due date)
    - Vendor name matching
    - Data source confidence

    Returns suggestions grouped by confidence level:
    - >= 95%: Auto-approved (if enabled)
    - 70-94%: Queued for review
    - < 70%: Flagged as needs manual match
    """
    # Get unreconciled payments
    payments_query = select(models.PaymentEvent).where(
        and_(
            models.PaymentEvent.user_id == current_user.id,
            models.PaymentEvent.is_reconciled == False
        )
    ).order_by(models.PaymentEvent.payment_date.desc())

    payments_result = await db.execute(payments_query)
    unreconciled_payments = payments_result.scalars().all()

    # Get unpaid schedules with their obligations
    schedules_query = select(models.ObligationSchedule).join(
        models.ObligationAgreement
    ).where(
        and_(
            models.ObligationAgreement.user_id == current_user.id,
            models.ObligationSchedule.status.in_(["scheduled", "due", "overdue"])
        )
    ).options(
        selectinload(models.ObligationSchedule.obligation)
    )

    schedules_result = await db.execute(schedules_query)
    unpaid_schedules = schedules_result.scalars().all()

    # Generate suggestions by matching payments to schedules
    suggestions = []
    auto_approved_count = 0
    pending_review_count = 0
    unmatched_count = 0

    # Default settings (TODO: load from user config)
    auto_approve_threshold = 0.95
    review_threshold = 0.70

    for payment in unreconciled_payments:
        best_match = None
        best_confidence = 0.0
        best_reasoning = ""

        for schedule in unpaid_schedules:
            obligation = schedule.obligation
            if not obligation:
                continue

            confidence, reasoning = _calculate_match_confidence(payment, schedule, obligation)

            if confidence > best_confidence:
                best_confidence = confidence
                best_match = (schedule, obligation)
                best_reasoning = reasoning

        if best_match and best_confidence >= review_threshold:
            schedule, obligation = best_match

            # Calculate variance
            variance_amount = None
            variance_percent = None
            if payment.amount and schedule.estimated_amount:
                variance_amount = payment.amount - schedule.estimated_amount
                if schedule.estimated_amount:
                    variance_percent = float(variance_amount / schedule.estimated_amount * 100)

            is_auto_approved = best_confidence >= auto_approve_threshold

            suggestion = ReconciliationSuggestion(
                id=f"sug_{payment.id}_{schedule.id}",
                payment_id=payment.id,
                payment=PaymentEventResponse.model_validate(payment),
                suggested_schedule_id=schedule.id,
                suggested_schedule=ObligationScheduleResponse.model_validate(schedule),
                suggested_obligation=ObligationAgreementResponse.model_validate(obligation),
                confidence=best_confidence,
                reasoning=best_reasoning,
                variance_amount=variance_amount,
                variance_percent=variance_percent,
                auto_approved=is_auto_approved,
                created_at=datetime.utcnow()
            )

            if is_auto_approved:
                auto_approved_count += 1
                if include_auto_approved:
                    suggestions.append(suggestion)
            else:
                pending_review_count += 1
                suggestions.append(suggestion)
        else:
            unmatched_count += 1

    return ReconciliationSuggestionList(
        suggestions=suggestions,
        total_count=len(suggestions),
        auto_approved_count=auto_approved_count,
        pending_review_count=pending_review_count,
        unmatched_count=unmatched_count
    )


@router.post("/reconciliation/approve", response_model=PaymentEventResponse)
async def approve_reconciliation(
    request: ApproveReconciliationRequest,
    current_user: models.User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Approve a reconciliation suggestion or manual match.

    Links the payment to the specified schedule and marks both as reconciled/paid.
    """
    # Get payment
    payment_query = select(models.PaymentEvent).where(
        models.PaymentEvent.id == request.payment_id
    )
    result = await db.execute(payment_query)
    payment = result.scalar_one_or_none()

    if not payment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Payment {request.payment_id} not found"
        )

    if payment.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to modify this payment"
        )

    # Get schedule
    schedule_query = select(models.ObligationSchedule).where(
        models.ObligationSchedule.id == request.schedule_id
    )
    result = await db.execute(schedule_query)
    schedule = result.scalar_one_or_none()

    if not schedule:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Schedule {request.schedule_id} not found"
        )

    # Verify schedule ownership via obligation
    obligation_query = select(models.ObligationAgreement).where(
        models.ObligationAgreement.id == schedule.obligation_id
    )
    result = await db.execute(obligation_query)
    obligation = result.scalar_one_or_none()

    if not obligation or obligation.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to reconcile with this schedule"
        )

    # Calculate variance
    if payment.amount and schedule.estimated_amount:
        payment.variance_vs_expected = payment.amount - schedule.estimated_amount

    # Link and reconcile
    payment.schedule_id = request.schedule_id
    payment.obligation_id = schedule.obligation_id
    payment.is_reconciled = True
    payment.reconciled_at = datetime.utcnow()

    schedule.status = "paid"

    await db.commit()
    await db.refresh(payment)

    return payment


@router.post("/reconciliation/approve-bulk", response_model=BulkReconciliationResult)
async def approve_bulk_reconciliation(
    request: BulkReconciliationRequest,
    current_user: models.User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Approve multiple reconciliation matches at once.

    Useful for quickly processing AI suggestions that have been reviewed.
    """
    successful = 0
    failed = 0
    errors = []

    for match in request.matches:
        try:
            # Get payment
            payment_query = select(models.PaymentEvent).where(
                and_(
                    models.PaymentEvent.id == match.payment_id,
                    models.PaymentEvent.user_id == current_user.id
                )
            )
            result = await db.execute(payment_query)
            payment = result.scalar_one_or_none()

            if not payment:
                failed += 1
                errors.append(f"Payment {match.payment_id} not found or not authorized")
                continue

            # Get schedule with obligation
            schedule_query = select(models.ObligationSchedule).join(
                models.ObligationAgreement
            ).where(
                and_(
                    models.ObligationSchedule.id == match.schedule_id,
                    models.ObligationAgreement.user_id == current_user.id
                )
            )
            result = await db.execute(schedule_query)
            schedule = result.scalar_one_or_none()

            if not schedule:
                failed += 1
                errors.append(f"Schedule {match.schedule_id} not found or not authorized")
                continue

            # Calculate variance
            if payment.amount and schedule.estimated_amount:
                payment.variance_vs_expected = payment.amount - schedule.estimated_amount

            # Link and reconcile
            payment.schedule_id = match.schedule_id
            payment.obligation_id = schedule.obligation_id
            payment.is_reconciled = True
            payment.reconciled_at = datetime.utcnow()

            schedule.status = "paid"
            successful += 1

        except Exception as e:
            failed += 1
            errors.append(f"Error processing {match.payment_id}: {str(e)}")

    await db.commit()

    return BulkReconciliationResult(
        successful=successful,
        failed=failed,
        errors=errors
    )


@router.post("/reconciliation/reject", response_model=PaymentEventResponse)
async def reject_reconciliation(
    request: RejectReconciliationRequest,
    current_user: models.User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Reject a reconciliation suggestion.

    The payment remains unreconciled and can be manually matched later.
    Optionally stores the rejection reason for audit purposes.
    """
    # Get payment
    payment_query = select(models.PaymentEvent).where(
        models.PaymentEvent.id == request.payment_id
    )
    result = await db.execute(payment_query)
    payment = result.scalar_one_or_none()

    if not payment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Payment {request.payment_id} not found"
        )

    if payment.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to modify this payment"
        )

    # Store rejection reason in notes if provided
    if request.reason:
        existing_notes = payment.notes or ""
        payment.notes = f"{existing_notes}\n[Reconciliation rejected: {request.reason}]".strip()

    await db.commit()
    await db.refresh(payment)

    return payment


@router.post("/reconciliation/revert", response_model=PaymentEventResponse)
async def revert_reconciliation(
    request: RevertReconciliationRequest,
    current_user: models.User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Revert a reconciliation (undo auto-approved or manually approved match).

    Unlinks the payment from its schedule and marks both as unreconciled/unpaid.
    """
    # Get payment
    payment_query = select(models.PaymentEvent).where(
        models.PaymentEvent.id == request.payment_id
    )
    result = await db.execute(payment_query)
    payment = result.scalar_one_or_none()

    if not payment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Payment {request.payment_id} not found"
        )

    if payment.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to modify this payment"
        )

    if not payment.is_reconciled:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Payment is not reconciled"
        )

    # Revert the schedule status if linked
    if payment.schedule_id:
        schedule_query = select(models.ObligationSchedule).where(
            models.ObligationSchedule.id == payment.schedule_id
        )
        result = await db.execute(schedule_query)
        schedule = result.scalar_one_or_none()

        if schedule:
            # Determine appropriate status based on due date
            today = date.today()
            if schedule.due_date < today:
                schedule.status = "overdue"
            elif schedule.due_date == today:
                schedule.status = "due"
            else:
                schedule.status = "scheduled"

    # Store revert reason in notes if provided
    if request.reason:
        existing_notes = payment.notes or ""
        payment.notes = f"{existing_notes}\n[Reconciliation reverted: {request.reason}]".strip()

    # Unlink and un-reconcile
    payment.schedule_id = None
    payment.obligation_id = None
    payment.is_reconciled = False
    payment.reconciled_at = None
    payment.variance_vs_expected = None

    await db.commit()
    await db.refresh(payment)

    return payment


@router.get("/reconciliation/forecast-impact", response_model=ForecastImpactSummary)
async def get_forecast_impact(
    current_user: models.User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Calculate how unreconciled items affect forecast accuracy.

    Returns an accuracy score and lists the top items impacting the forecast.
    """
    from decimal import Decimal

    # Get unreconciled payments
    payments_query = select(models.PaymentEvent).where(
        and_(
            models.PaymentEvent.user_id == current_user.id,
            models.PaymentEvent.is_reconciled == False
        )
    ).order_by(models.PaymentEvent.payment_date.desc())

    result = await db.execute(payments_query)
    unreconciled = result.scalars().all()

    # Get total recent payment volume for comparison
    thirty_days_ago = date.today() - timedelta(days=30)
    total_query = select(models.PaymentEvent).where(
        and_(
            models.PaymentEvent.user_id == current_user.id,
            models.PaymentEvent.payment_date >= thirty_days_ago
        )
    )
    total_result = await db.execute(total_query)
    all_recent_payments = total_result.scalars().all()

    total_volume = sum(float(p.amount or 0) for p in all_recent_payments)
    unreconciled_volume = sum(float(p.amount or 0) for p in unreconciled)

    # Calculate impact percentage
    impact_percent = (unreconciled_volume / total_volume * 100) if total_volume > 0 else 0

    # Calculate accuracy score (inverse of impact, capped at 100)
    accuracy_score = max(0, min(100, 100 - impact_percent))

    # Determine severity
    if accuracy_score >= 85:
        severity = "healthy"
    elif accuracy_score >= 70:
        severity = "warning"
    else:
        severity = "critical"

    # Build top impacting items
    top_items = []
    today = date.today()
    for payment in unreconciled[:10]:  # Top 10
        days_old = (today - payment.payment_date).days if payment.payment_date else 0
        top_items.append(ForecastImpactItem(
            payment=PaymentEventResponse.model_validate(payment),
            impact_amount=payment.amount or Decimal("0"),
            days_old=days_old
        ))

    return ForecastImpactSummary(
        accuracy_score=accuracy_score,
        unreconciled_count=len(unreconciled),
        unreconciled_amount=Decimal(str(unreconciled_volume)),
        impact_percent=impact_percent,
        top_impacting_items=top_items,
        severity=severity
    )


@router.get("/reconciliation/auto-approved", response_model=List[PaymentEventResponse])
async def list_auto_approved(
    current_user: models.User = Depends(get_current_user),
    hours: int = 24,
    db: AsyncSession = Depends(get_db)
):
    """
    Get recently auto-approved reconciliations for audit/review.

    Default shows last 24 hours, adjustable via hours parameter.
    """
    cutoff = datetime.utcnow() - timedelta(hours=hours)

    query = select(models.PaymentEvent).where(
        and_(
            models.PaymentEvent.user_id == current_user.id,
            models.PaymentEvent.is_reconciled == True,
            models.PaymentEvent.reconciled_at >= cutoff
        )
    ).order_by(models.PaymentEvent.reconciled_at.desc())

    result = await db.execute(query)
    payments = result.scalars().all()

    return payments


@router.get("/reconciliation/queue-summary", response_model=ReconciliationQueueSummary)
async def get_queue_summary(
    current_user: models.User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Get a summary of the reconciliation queue for UI display.

    Returns counts for each queue section and overall forecast accuracy.
    """
    # Get unreconciled payments
    payments_query = select(models.PaymentEvent).where(
        and_(
            models.PaymentEvent.user_id == current_user.id,
            models.PaymentEvent.is_reconciled == False
        )
    )
    result = await db.execute(payments_query)
    unreconciled = result.scalars().all()

    # Get recently auto-approved (last 24h)
    cutoff = datetime.utcnow() - timedelta(hours=24)
    auto_approved_query = select(models.PaymentEvent).where(
        and_(
            models.PaymentEvent.user_id == current_user.id,
            models.PaymentEvent.is_reconciled == True,
            models.PaymentEvent.reconciled_at >= cutoff
        )
    )
    result = await db.execute(auto_approved_query)
    recently_approved = result.scalars().all()

    # Get forecast impact for accuracy
    impact = await get_forecast_impact(current_user, db)

    # For now, estimate queue breakdown based on simple heuristics
    # In production, this would use the full suggestion matching
    total_unreconciled = len(unreconciled)

    # Rough estimates (in production, run actual matching)
    affecting_forecast = sum(1 for p in unreconciled if p.amount and float(p.amount) > 1000)
    ai_suggestions = int(total_unreconciled * 0.6)  # Estimate 60% can be matched
    needs_manual = total_unreconciled - ai_suggestions

    return ReconciliationQueueSummary(
        total_pending=total_unreconciled,
        affecting_forecast=affecting_forecast,
        ai_suggestions=ai_suggestions,
        needs_manual_match=needs_manual,
        recently_auto_approved=len(recently_approved),
        forecast_accuracy=impact.accuracy_score
    )
