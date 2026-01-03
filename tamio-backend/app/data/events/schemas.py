"""Pydantic schemas for cash event validation."""
from pydantic import BaseModel
from datetime import date, datetime
from typing import Optional
from decimal import Decimal


class CashEventResponse(BaseModel):
    """Schema for cash event response."""
    id: str
    user_id: str
    date: date
    week_number: int
    amount: Decimal
    direction: str
    event_type: str
    category: Optional[str] = None
    client_id: Optional[str] = None
    bucket_id: Optional[str] = None
    confidence: str
    confidence_reason: Optional[str] = None
    is_recurring: bool
    recurrence_pattern: Optional[str] = None
    notes: Optional[str] = None
    created_at: datetime
    updated_at: Optional[datetime] = None

    model_config = {"from_attributes": True}
