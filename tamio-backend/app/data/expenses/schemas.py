"""Pydantic schemas for expense bucket validation."""
from pydantic import BaseModel, Field
from datetime import date, datetime
from typing import Optional, Literal, List, Any
from decimal import Decimal


class ExpenseBucketCreate(BaseModel):
    """Schema for creating an expense bucket."""
    user_id: str
    name: str = Field(..., min_length=1, max_length=255)
    category: Literal["payroll", "rent", "contractors", "software", "marketing", "other"]
    bucket_type: Literal["fixed", "variable"]
    monthly_amount: Decimal = Field(..., gt=0, decimal_places=2)
    currency: str = Field(default="USD", pattern="^[A-Z]{3}$")
    # Accept both old (high/medium/low) and new (essential/important/discretionary) priority values
    priority: Literal["high", "medium", "low", "essential", "important", "discretionary"]
    is_stable: bool = True
    due_day: Optional[int] = Field(default=15, ge=1, le=31)  # Day of month for payment
    frequency: Optional[str] = Field(default="monthly")  # "monthly" | "weekly" | "quarterly"
    employee_count: Optional[int] = Field(None, ge=0)
    notes: Optional[str] = None


class ExpenseBucketResponse(BaseModel):
    """Schema for expense bucket response."""
    id: str
    user_id: str
    name: str
    category: str
    bucket_type: str
    monthly_amount: Decimal
    currency: str
    priority: str
    is_stable: bool
    due_day: Optional[int] = 15
    frequency: Optional[str] = "monthly"
    employee_count: Optional[int] = None
    notes: Optional[str] = None

    # Sync fields
    source: str = "manual"  # "manual" | "xero" | "quickbooks"
    xero_contact_id: Optional[str] = None
    xero_repeating_bill_id: Optional[str] = None
    quickbooks_vendor_id: Optional[str] = None
    sync_status: Optional[str] = None
    last_synced_at: Optional[datetime] = None
    sync_error: Optional[str] = None
    locked_fields: List[str] = []

    created_at: datetime
    updated_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class ExpenseBucketUpdate(BaseModel):
    """Schema for updating an expense bucket."""
    name: Optional[str] = None
    category: Optional[Literal["payroll", "rent", "contractors", "software", "marketing", "other"]] = None
    bucket_type: Optional[Literal["fixed", "variable"]] = None
    monthly_amount: Optional[Decimal] = Field(None, gt=0, decimal_places=2)
    currency: Optional[str] = None
    priority: Optional[Literal["high", "medium", "low"]] = None
    is_stable: Optional[bool] = None
    employee_count: Optional[int] = Field(None, ge=0)
    notes: Optional[str] = None


class ExpenseBucketCreateForOnboarding(BaseModel):
    """Schema for creating an expense bucket during onboarding (no user_id required)."""
    name: str = Field(..., min_length=1, max_length=255)
    category: Literal["payroll", "rent", "software", "contractors", "marketing", "other"]
    bucket_type: Literal["fixed", "variable", "hybrid"] = "fixed"
    monthly_amount: Decimal = Field(..., ge=0, decimal_places=2)
    currency: str = Field(default="USD", pattern="^[A-Z]{3}$")
    priority: Literal["essential", "important", "discretionary"] = "important"
    is_stable: bool = True
    due_day: Optional[int] = Field(default=15, ge=1, le=31)  # Day of month for payment
    frequency: Optional[str] = Field(default="monthly")  # "monthly" | "weekly" | "quarterly"
    employee_count: Optional[int] = None
    notes: Optional[str] = None


# CashEventResponse is defined inline to avoid circular imports
class _CashEventResponseForExpense(BaseModel):
    """Schema for cash event response (inline to avoid circular imports)."""
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


class ExpenseBucketWithEventsResponse(BaseModel):
    """Expense bucket response with generated events."""
    bucket: ExpenseBucketResponse
    generated_events: List[_CashEventResponseForExpense]
