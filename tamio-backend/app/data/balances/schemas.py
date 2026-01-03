"""Pydantic schemas for cash account/balance validation."""
from pydantic import BaseModel, Field
from datetime import date, datetime
from typing import Optional, List
from decimal import Decimal


class CashAccountCreate(BaseModel):
    """Schema for creating a cash account."""
    account_name: str = Field(..., min_length=1, max_length=255)
    balance: Decimal = Field(..., ge=0, decimal_places=2)
    currency: str = Field(default="USD", pattern="^[A-Z]{3}$")
    as_of_date: date


class CashAccountResponse(BaseModel):
    """Schema for cash account response."""
    id: str
    user_id: str
    account_name: str
    balance: Decimal
    currency: str
    as_of_date: date
    created_at: datetime
    updated_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class CashPositionCreate(BaseModel):
    """Schema for creating cash position (Page 1)."""
    user_id: str
    accounts: List[CashAccountCreate]


class CashAccountsUpdate(BaseModel):
    """Schema for updating cash accounts (user_id from URL)."""
    accounts: List[CashAccountCreate]


class CashPositionResponse(BaseModel):
    """Schema for cash position response."""
    accounts: List[CashAccountResponse]
    total_starting_cash: Decimal
