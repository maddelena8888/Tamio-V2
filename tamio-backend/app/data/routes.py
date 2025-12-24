"""Data API routes - handles all manual data input."""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete
from typing import List
from datetime import date, timedelta
from decimal import Decimal

from app.database import get_db
from app.data import models, schemas
from app.data.event_generator import generate_events_from_client, generate_events_from_bucket

router = APIRouter()


# ============================================================================
# USER / AUTH ROUTES
# ============================================================================

@router.post("/auth/signup", response_model=schemas.UserResponse)
async def signup(user_data: schemas.UserCreate, db: AsyncSession = Depends(get_db)):
    """Create a new user."""
    # Check if email already exists
    result = await db.execute(
        select(models.User).where(models.User.email == user_data.email)
    )
    if result.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Email already registered")

    user = models.User(
        email=user_data.email,
        base_currency=user_data.base_currency
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


# ============================================================================
# PAGE 1: CASH POSITION ROUTES
# ============================================================================

@router.post("/cash-position", response_model=schemas.CashPositionResponse)
async def create_cash_position(
    data: schemas.CashPositionCreate,
    db: AsyncSession = Depends(get_db)
):
    """Create cash position (one or more accounts)."""
    # Verify user exists
    result = await db.execute(
        select(models.User).where(models.User.id == data.user_id)
    )
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Create accounts
    accounts = []
    for acc_data in data.accounts:
        account = models.CashAccount(
            user_id=data.user_id,
            account_name=acc_data.account_name,
            balance=acc_data.balance,
            currency=acc_data.currency,
            as_of_date=acc_data.as_of_date
        )
        db.add(account)
        accounts.append(account)

    await db.commit()
    for acc in accounts:
        await db.refresh(acc)

    total = sum(acc.balance for acc in accounts)

    return schemas.CashPositionResponse(
        accounts=accounts,
        total_starting_cash=total
    )


@router.get("/cash-position", response_model=schemas.CashPositionResponse)
async def get_cash_position(
    user_id: str = Query(...),
    db: AsyncSession = Depends(get_db)
):
    """Get current cash position for a user."""
    result = await db.execute(
        select(models.CashAccount).where(models.CashAccount.user_id == user_id)
    )
    accounts = result.scalars().all()

    total = sum(acc.balance for acc in accounts)

    return schemas.CashPositionResponse(
        accounts=accounts,
        total_starting_cash=total
    )


# ============================================================================
# PAGE 2: CLIENT ROUTES (CASH IN)
# ============================================================================

@router.post("/clients", response_model=schemas.ClientWithEventsResponse)
async def create_client(
    data: schemas.ClientCreate,
    db: AsyncSession = Depends(get_db)
):
    """Create a client and auto-generate cash events."""
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
        notes=data.notes
    )
    db.add(client)
    await db.commit()
    await db.refresh(client)

    # Generate cash events from billing config
    events = await generate_events_from_client(db, client)

    return schemas.ClientWithEventsResponse(
        client=client,
        generated_events=events
    )


@router.get("/clients", response_model=List[schemas.ClientResponse])
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


@router.put("/clients/{client_id}", response_model=schemas.ClientWithEventsResponse)
async def update_client(
    client_id: str,
    data: schemas.ClientUpdate,
    db: AsyncSession = Depends(get_db)
):
    """Update a client and regenerate cash events."""
    result = await db.execute(
        select(models.Client).where(models.Client.id == client_id)
    )
    client = result.scalar_one_or_none()
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")

    # Update fields
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(client, field, value)

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

    return schemas.ClientWithEventsResponse(
        client=client,
        generated_events=events
    )


@router.delete("/clients/{client_id}")
async def delete_client(
    client_id: str,
    db: AsyncSession = Depends(get_db)
):
    """Soft delete a client."""
    result = await db.execute(
        select(models.Client).where(models.Client.id == client_id)
    )
    client = result.scalar_one_or_none()
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")

    client.status = "deleted"
    await db.commit()

    return {"message": "Client deleted successfully"}


# ============================================================================
# PAGE 3: EXPENSE BUCKET ROUTES (CASH OUT)
# ============================================================================

@router.post("/expenses", response_model=schemas.ExpenseBucketWithEventsResponse)
async def create_expense_bucket(
    data: schemas.ExpenseBucketCreate,
    db: AsyncSession = Depends(get_db)
):
    """Create an expense bucket and auto-generate cash events."""
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
        notes=data.notes
    )
    db.add(bucket)
    await db.commit()
    await db.refresh(bucket)

    # Generate cash events
    events = await generate_events_from_bucket(db, bucket)

    return schemas.ExpenseBucketWithEventsResponse(
        bucket=bucket,
        generated_events=events
    )


@router.get("/expenses", response_model=List[schemas.ExpenseBucketResponse])
async def get_expense_buckets(
    user_id: str = Query(...),
    db: AsyncSession = Depends(get_db)
):
    """Get all expense buckets for a user."""
    result = await db.execute(
        select(models.ExpenseBucket).where(models.ExpenseBucket.user_id == user_id)
    )
    return result.scalars().all()


@router.put("/expenses/{bucket_id}", response_model=schemas.ExpenseBucketWithEventsResponse)
async def update_expense_bucket(
    bucket_id: str,
    data: schemas.ExpenseBucketUpdate,
    db: AsyncSession = Depends(get_db)
):
    """Update an expense bucket and regenerate cash events."""
    result = await db.execute(
        select(models.ExpenseBucket).where(models.ExpenseBucket.id == bucket_id)
    )
    bucket = result.scalar_one_or_none()
    if not bucket:
        raise HTTPException(status_code=404, detail="Expense bucket not found")

    # Update fields
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(bucket, field, value)

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

    return schemas.ExpenseBucketWithEventsResponse(
        bucket=bucket,
        generated_events=events
    )


@router.delete("/expenses/{bucket_id}")
async def delete_expense_bucket(
    bucket_id: str,
    db: AsyncSession = Depends(get_db)
):
    """Delete an expense bucket and its events."""
    result = await db.execute(
        select(models.ExpenseBucket).where(models.ExpenseBucket.id == bucket_id)
    )
    bucket = result.scalar_one_or_none()
    if not bucket:
        raise HTTPException(status_code=404, detail="Expense bucket not found")

    await db.delete(bucket)
    await db.commit()

    return {"message": "Expense bucket deleted successfully"}


# ============================================================================
# COMBINED ONBOARDING ROUTE
# ============================================================================

@router.post("/onboarding", response_model=schemas.OnboardingResponse)
async def complete_onboarding(
    data: schemas.OnboardingCreate,
    db: AsyncSession = Depends(get_db)
):
    """
    Complete full onboarding in one transaction.
    Creates user, cash accounts, clients, and expense buckets.
    """
    # Create user
    user = models.User(
        email=data.user.email,
        base_currency=data.user.base_currency
    )
    db.add(user)
    await db.flush()  # Get user ID

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

    await db.commit()

    # Refresh all objects
    await db.refresh(user)
    for acc in accounts:
        await db.refresh(acc)
    for client in clients:
        await db.refresh(client)
    for bucket in buckets:
        await db.refresh(bucket)

    # Generate events from clients and buckets
    total_events = 0
    for client in clients:
        await generate_events_from_client(db, client)
        total_events += 1

    for bucket in buckets:
        await generate_events_from_bucket(db, bucket)
        total_events += 1

    total_cash = sum(acc.balance for acc in accounts)

    return schemas.OnboardingResponse(
        user=user,
        cash_position=schemas.CashPositionResponse(
            accounts=accounts,
            total_starting_cash=total_cash
        ),
        clients=clients,
        expenses=buckets,
        total_generated_events=total_events
    )


# ============================================================================
# REGENERATE EVENTS ROUTE
# ============================================================================

@router.post("/regenerate-events")
async def regenerate_all_events(
    user_id: str = Query(...),
    db: AsyncSession = Depends(get_db)
):
    """Regenerate all cash events for a user's clients and expenses."""
    from app.scenarios.models import ScenarioEvent

    # Verify user exists
    result = await db.execute(
        select(models.User).where(models.User.id == user_id)
    )
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="User not found")

    # Get IDs of events we're about to delete
    result = await db.execute(
        select(models.CashEvent.id).where(
            models.CashEvent.user_id == user_id,
            models.CashEvent.date >= date.today()
        )
    )
    event_ids_to_delete = [row[0] for row in result.fetchall()]

    # Clear references in scenario_events first (set original_event_id to NULL)
    if event_ids_to_delete:
        await db.execute(
            ScenarioEvent.__table__.update()
            .where(ScenarioEvent.original_event_id.in_(event_ids_to_delete))
            .values(original_event_id=None)
        )

    # Delete all future events
    await db.execute(
        delete(models.CashEvent).where(
            models.CashEvent.user_id == user_id,
            models.CashEvent.date >= date.today()
        )
    )
    await db.commit()

    # Get all active clients
    result = await db.execute(
        select(models.Client).where(
            models.Client.user_id == user_id,
            models.Client.status != "deleted"
        )
    )
    clients = result.scalars().all()

    # Get all expense buckets
    result = await db.execute(
        select(models.ExpenseBucket).where(
            models.ExpenseBucket.user_id == user_id
        )
    )
    buckets = result.scalars().all()

    # Regenerate events
    total_events = 0

    for client in clients:
        events = await generate_events_from_client(db, client)
        total_events += len(events)

    for bucket in buckets:
        events = await generate_events_from_bucket(db, bucket)
        total_events += len(events)

    return {
        "message": "Events regenerated successfully",
        "total_events": total_events,
        "clients_processed": len(clients),
        "expenses_processed": len(buckets)
    }
