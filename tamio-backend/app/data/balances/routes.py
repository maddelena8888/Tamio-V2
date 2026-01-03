"""Cash Account / Balance API routes."""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete
from typing import List

from app.database import get_db
from app.data import models
from app.data.balances.schemas import (
    CashAccountCreate,
    CashAccountResponse,
    CashPositionCreate,
    CashAccountsUpdate,
    CashPositionResponse,
)

router = APIRouter()


@router.post("/cash-position", response_model=CashPositionResponse)
async def create_cash_position(
    data: CashPositionCreate,
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

    return CashPositionResponse(
        accounts=accounts,
        total_starting_cash=total
    )


@router.get("/cash-position", response_model=CashPositionResponse)
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

    return CashPositionResponse(
        accounts=accounts,
        total_starting_cash=total
    )


@router.put("/cash-accounts/{user_id}", response_model=CashPositionResponse)
async def update_cash_accounts(
    user_id: str,
    data: CashAccountsUpdate,
    db: AsyncSession = Depends(get_db)
):
    """Update cash accounts for a user (replaces all existing accounts)."""
    # Verify user exists
    result = await db.execute(
        select(models.User).where(models.User.id == user_id)
    )
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Delete existing accounts
    await db.execute(
        delete(models.CashAccount).where(models.CashAccount.user_id == user_id)
    )

    # Create new accounts
    accounts = []
    for acc_data in data.accounts:
        account = models.CashAccount(
            user_id=user_id,
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

    return CashPositionResponse(
        accounts=accounts,
        total_starting_cash=total
    )
