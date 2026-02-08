"""
Pydantic schemas for UserConfiguration CRUD operations.
"""
from datetime import datetime
from decimal import Decimal
from typing import Optional, Literal

from pydantic import BaseModel, Field


class UserConfigurationBase(BaseModel):
    """Base schema with common fields."""
    obligations_buffer_amount: Optional[Decimal] = Field(
        default=Decimal("0"),
        ge=0,
        description="Minimum cash buffer for obligations in base currency"
    )
    runway_buffer_months: Optional[int] = Field(
        default=6,
        ge=1,
        le=24,
        description="Runway warning threshold in months"
    )
    late_payment_threshold_days: Optional[int] = Field(
        default=7,
        ge=1,
        le=90,
        description="Days after due date to flag as overdue"
    )
    unexpected_expense_threshold_pct: Optional[Decimal] = Field(
        default=Decimal("20.0"),
        ge=5,
        le=100,
        description="Percentage spike to flag as unexpected expense"
    )
    safety_mode: Optional[Literal["conservative", "normal", "aggressive"]] = Field(
        default="normal",
        description="Detection sensitivity mode"
    )
    payroll_check_days_before: Optional[int] = Field(
        default=7,
        ge=1,
        le=30,
        description="Days before payroll to check safety"
    )
    payroll_buffer_percent: Optional[Decimal] = Field(
        default=Decimal("10.0"),
        ge=0,
        le=50,
        description="Minimum buffer after payroll as percentage"
    )
    payment_cluster_threshold_pct: Optional[Decimal] = Field(
        default=Decimal("40.0"),
        ge=10,
        le=100,
        description="Max percentage of cash due in one week"
    )


class UserConfigurationCreate(UserConfigurationBase):
    """Schema for creating user configuration."""
    user_id: str = Field(..., description="User ID (foreign key)")


class UserConfigurationUpdate(UserConfigurationBase):
    """Schema for updating user configuration. All fields optional."""
    pass


class UserConfigurationResponse(BaseModel):
    """Schema for user configuration response."""
    user_id: str
    obligations_buffer_amount: Decimal
    runway_buffer_months: int
    late_payment_threshold_days: int
    unexpected_expense_threshold_pct: Decimal
    safety_mode: str
    payroll_check_days_before: int
    payroll_buffer_percent: Decimal
    payment_cluster_threshold_pct: Decimal
    created_at: datetime
    updated_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class UserConfigurationWithDefaults(BaseModel):
    """
    Schema showing all configuration fields with default values.
    Used for documentation and creating defaults.
    """
    obligations_buffer_amount: Decimal = Decimal("0")
    runway_buffer_months: int = 6
    late_payment_threshold_days: int = 7
    unexpected_expense_threshold_pct: Decimal = Decimal("20.0")
    safety_mode: str = "normal"
    payroll_check_days_before: int = 7
    payroll_buffer_percent: Decimal = Decimal("10.0")
    payment_cluster_threshold_pct: Decimal = Decimal("40.0")
