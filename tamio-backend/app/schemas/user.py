"""Pydantic schemas for user validation."""
from pydantic import BaseModel, Field, EmailStr
from datetime import datetime


class UserCreate(BaseModel):
    """Schema for creating a user."""
    email: EmailStr
    base_currency: str = Field(default="USD", pattern="^[A-Z]{3}$")


class UserResponse(BaseModel):
    """Schema for user response."""
    id: str
    email: str
    company_name: str | None = None
    base_currency: str
    created_at: datetime

    model_config = {"from_attributes": True}
