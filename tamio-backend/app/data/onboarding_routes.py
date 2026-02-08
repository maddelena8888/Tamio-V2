"""Onboarding API routes - combined onboarding and migration endpoints."""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from datetime import date

from app.database import get_db
from app.data import models
from app.data.onboarding import OnboardingCreate, OnboardingResponse
from app.data.balances.schemas import CashPositionResponse
from app.data.migration import backfill_client_canonical_structure
from app.services.obligations import ObligationService

router = APIRouter()


@router.post("/onboarding", response_model=OnboardingResponse)
async def complete_onboarding(
    data: OnboardingCreate,
    db: AsyncSession = Depends(get_db)
):
    """
    Complete full onboarding in one transaction.
    Creates or uses existing user, then creates cash accounts, clients, and expense buckets.
    """
    # Check if user already exists (for authenticated onboarding)
    result = await db.execute(
        select(models.User).where(models.User.email == data.user.email)
    )
    user = result.scalar_one_or_none()

    if user is None:
        # Create new user
        user = models.User(
            email=data.user.email,
            base_currency=data.user.base_currency
        )
        db.add(user)
        await db.flush()  # Get user ID
    else:
        # Use existing user - update base_currency if provided
        if data.user.base_currency:
            user.base_currency = data.user.base_currency

    # Create cash accounts
    accounts = []
    for acc_data in data.cash_position:
        account = models.CashAccount(
            user_id=user.id,
            account_name=acc_data.account_name,
            balance=acc_data.balance,
            currency=acc_data.currency,
            as_of_date=acc_data.as_of_date
        )
        db.add(account)
        accounts.append(account)

    # Create clients
    clients = []
    for client_data in data.clients:
        client = models.Client(
            user_id=user.id,
            name=client_data.name,
            client_type=client_data.client_type,
            currency=client_data.currency,
            status=client_data.status,
            payment_behavior=client_data.payment_behavior,
            churn_risk=client_data.churn_risk,
            scope_risk=client_data.scope_risk,
            billing_config=client_data.billing_config,
            notes=client_data.notes
        )
        db.add(client)
        clients.append(client)

    # Create expense buckets
    buckets = []
    for bucket_data in data.expenses:
        bucket = models.ExpenseBucket(
            user_id=user.id,
            name=bucket_data.name,
            category=bucket_data.category,
            bucket_type=bucket_data.bucket_type,
            monthly_amount=bucket_data.monthly_amount,
            currency=bucket_data.currency,
            priority=bucket_data.priority,
            is_stable=bucket_data.is_stable,
            due_day=bucket_data.due_day,
            frequency=bucket_data.frequency,
            employee_count=bucket_data.employee_count,
            notes=bucket_data.notes
        )
        db.add(bucket)
        buckets.append(bucket)

    # Create ObligationAgreements from expense buckets
    obligations = []
    for bucket_data in data.expenses:
        # Map category to obligation_type
        obligation_type_map = {
            "payroll": "payroll",
            "rent": "lease",
            "contractors": "contractor",
            "software": "subscription",
            "marketing": "other",
            "other": "other",
            "other_fixed": "other"
        }

        # Build notes with metadata
        notes_parts = [f"Priority: {bucket_data.priority}"]
        if bucket_data.employee_count:
            notes_parts.append(f"Employees: {bucket_data.employee_count}")
        if bucket_data.notes:
            notes_parts.append(bucket_data.notes)

        obligation = models.ObligationAgreement(
            user_id=user.id,
            obligation_type=obligation_type_map.get(bucket_data.category, "other"),
            amount_type="fixed" if bucket_data.is_stable else "variable",
            amount_source="manual_entry",
            base_amount=bucket_data.monthly_amount,
            currency=bucket_data.currency,
            frequency=bucket_data.frequency,
            start_date=date.today(),
            end_date=None,  # Ongoing
            category=bucket_data.category,
            confidence="high" if bucket_data.is_stable else "medium",
            vendor_name=bucket_data.name,
            notes=" | ".join(notes_parts)
        )
        db.add(obligation)
        obligations.append(obligation)

    await db.commit()

    # Refresh all objects
    await db.refresh(user)
    for acc in accounts:
        await db.refresh(acc)
    for client in clients:
        await db.refresh(client)
    for bucket in buckets:
        await db.refresh(bucket)
    for obligation in obligations:
        await db.refresh(obligation)

    # Generate obligations from clients and buckets
    obligation_service = ObligationService(db)
    total_obligations = 0

    for client in clients:
        await obligation_service.create_obligation_from_client(client)
        total_obligations += 1

    for bucket in buckets:
        await obligation_service.create_obligation_from_expense(bucket)
        total_obligations += 1

    total_cash = sum(acc.balance for acc in accounts)

    return OnboardingResponse(
        user=user,
        cash_position=CashPositionResponse(
            accounts=accounts,
            total_starting_cash=total_cash
        ),
        clients=clients,
        expenses=buckets,
        total_generated_events=total_obligations  # Now represents obligations, not events
    )


@router.post("/onboarding/complete")
async def mark_onboarding_complete(
    user_id: str = Query(..., description="User ID to mark as onboarded"),
    db: AsyncSession = Depends(get_db)
):
    """
    Mark a user's onboarding as complete.
    This is used when skipping onboarding or after completing it via integration.
    """
    result = await db.execute(
        select(models.User).where(models.User.id == user_id)
    )
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    user.has_completed_onboarding = True
    await db.commit()

    return {"success": True, "message": "Onboarding marked as complete"}


@router.post("/migrate/backfill-clients")
async def migrate_backfill_clients(
    user_id: str = Query(..., description="User ID to migrate clients for"),
    db: AsyncSession = Depends(get_db)
):
    """
    Backfill canonical structure on existing clients.

    This endpoint ensures all clients have:
    - payment_behavior (defaults to "unknown")
    - churn_risk (defaults to "low")
    - scope_risk (defaults to "low")
    - billing_config with proper structure and "source" field

    Use this after upgrading to canonical client structure.
    """
    stats = await backfill_client_canonical_structure(db, user_id)
    return stats
