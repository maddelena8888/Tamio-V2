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
from app.auth.dependencies import get_current_user

router = APIRouter()


@router.post("/cash-position", response_model=CashPositionResponse)
async def create_cash_position(
    data: CashPositionCreate,
    current_user: models.User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Create cash position (one or more accounts) for the authenticated user."""
    # Create accounts using authenticated user's ID
    accounts = []
    for acc_data in data.accounts:
        account = models.CashAccount(
            user_id=current_user.id,
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
    current_user: models.User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get current cash position for the authenticated user."""
    result = await db.execute(
        select(models.CashAccount).where(models.CashAccount.user_id == current_user.id)
    )
    accounts = result.scalars().all()

    total = sum(acc.balance for acc in accounts)

    return CashPositionResponse(
        accounts=accounts,
        total_starting_cash=total
    )


@router.put("/cash-accounts", response_model=CashPositionResponse)
async def update_cash_accounts(
    data: CashAccountsUpdate,
    current_user: models.User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Update cash accounts for the authenticated user (replaces all existing accounts)."""
    # Delete existing accounts for this user
    await db.execute(
        delete(models.CashAccount).where(models.CashAccount.user_id == current_user.id)
    )

    # Create new accounts
    accounts = []
    for acc_data in data.accounts:
        account = models.CashAccount(
            user_id=current_user.id,
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
