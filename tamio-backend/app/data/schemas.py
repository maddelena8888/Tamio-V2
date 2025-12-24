"""Pydantic schemas for data validation."""
from pydantic import BaseModel, Field, EmailStr
from datetime import date, datetime
from typing import Optional, List, Dict, Any, Literal
from decimal import Decimal


# ============================================================================
# USER SCHEMAS
# ============================================================================

class UserCreate(BaseModel):
    """Schema for creating a user."""
    email: EmailStr
    base_currency: str = Field(default="USD", pattern="^[A-Z]{3}$")


class UserResponse(BaseModel):
    """Schema for user response."""
    id: str
    email: str
    base_currency: str
    created_at: datetime

    model_config = {"from_attributes": True}


# ============================================================================
# PAGE 1: CASH POSITION SCHEMAS
# ============================================================================

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


class CashPositionResponse(BaseModel):
    """Schema for cash position response."""
    accounts: List[CashAccountResponse]
    total_starting_cash: Decimal


# ============================================================================
# PAGE 2: CLIENT SCHEMAS (CASH IN)
# ============================================================================

class ClientCreate(BaseModel):
    """Schema for creating a client."""
    user_id: str
    name: str = Field(..., min_length=1, max_length=255)
    client_type: Literal["retainer", "project", "usage", "mixed"]
    currency: str = Field(default="USD", pattern="^[A-Z]{3}$")
    status: Literal["active", "paused", "deleted"] = "active"

    # Risk indicators
    payment_behavior: Optional[Literal["on_time", "delayed", "unknown"]] = None
    churn_risk: Optional[Literal["low", "medium", "high"]] = None
    scope_risk: Optional[Literal["low", "medium", "high"]] = None

    # Billing config (JSONB - flexible structure)
    billing_config: Dict[str, Any]

    # Optional
    notes: Optional[str] = None


class ClientResponse(BaseModel):
    """Schema for client response."""
    id: str
    user_id: str
    name: str
    client_type: str
    currency: str
    status: str
    payment_behavior: Optional[str] = None
    churn_risk: Optional[str] = None
    scope_risk: Optional[str] = None
    billing_config: Dict[str, Any]
    notes: Optional[str] = None
    created_at: datetime
    updated_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class ClientUpdate(BaseModel):
    """Schema for updating a client."""
    name: Optional[str] = None
    client_type: Optional[Literal["retainer", "project", "usage", "mixed"]] = None
    currency: Optional[str] = None
    status: Optional[Literal["active", "paused", "deleted"]] = None
    payment_behavior: Optional[Literal["on_time", "delayed", "unknown"]] = None
    churn_risk: Optional[Literal["low", "medium", "high"]] = None
    scope_risk: Optional[Literal["low", "medium", "high"]] = None
    billing_config: Optional[Dict[str, Any]] = None
    notes: Optional[str] = None


# ============================================================================
# PAGE 3: EXPENSE BUCKET SCHEMAS (CASH OUT)
# ============================================================================

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


# ============================================================================
# CASH EVENT SCHEMAS
# ============================================================================

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


# ============================================================================
# COMBINED ONBOARDING SCHEMAS
# ============================================================================

class ClientCreateForOnboarding(BaseModel):
    """Schema for creating a client during onboarding (no user_id required)."""
    name: str = Field(..., min_length=1, max_length=255)
    client_type: Literal["retainer", "project", "usage", "mixed"]
    currency: str = Field(default="USD", pattern="^[A-Z]{3}$")
    status: Literal["active", "paused", "deleted"] = "active"
    payment_behavior: Optional[Literal["on_time", "delayed", "unknown"]] = None
    churn_risk: Optional[Literal["low", "medium", "high"]] = None
    scope_risk: Optional[Literal["low", "medium", "high"]] = None
    billing_config: Dict[str, Any]
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


class OnboardingCreate(BaseModel):
    """Schema for complete onboarding (all 3 pages)."""
    user: UserCreate
    cash_position: List[CashAccountCreate]
    clients: List[ClientCreateForOnboarding]
    expenses: List[ExpenseBucketCreateForOnboarding]


class OnboardingResponse(BaseModel):
    """Schema for onboarding response."""
    user: UserResponse
    cash_position: CashPositionResponse
    clients: List[ClientResponse]
    expenses: List[ExpenseBucketResponse]
    total_generated_events: int


# ============================================================================
# RESPONSE WRAPPERS
# ============================================================================

class ClientWithEventsResponse(BaseModel):
    """Client response with generated events."""
    client: ClientResponse
    generated_events: List[CashEventResponse]


class ExpenseBucketWithEventsResponse(BaseModel):
    """Expense bucket response with generated events."""
    bucket: ExpenseBucketResponse
    generated_events: List[CashEventResponse]
