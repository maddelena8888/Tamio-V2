"""Pydantic schemas for client validation."""
from pydantic import BaseModel, Field
from datetime import date, datetime
from typing import Optional, Dict, Any, Literal, List, TYPE_CHECKING
from decimal import Decimal


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

    # Sync fields
    source: str = "manual"  # "manual" | "xero" | "quickbooks"
    xero_contact_id: Optional[str] = None
    xero_repeating_invoice_id: Optional[str] = None
    quickbooks_customer_id: Optional[str] = None
    sync_status: Optional[str] = None
    last_synced_at: Optional[datetime] = None
    sync_error: Optional[str] = None
    locked_fields: List[str] = []

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


# CashEventResponse is defined inline to avoid circular imports
class _CashEventResponseForClient(BaseModel):
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


class ClientWithEventsResponse(BaseModel):
    """Client response with generated events."""
    client: ClientResponse
    generated_events: List[_CashEventResponseForClient]
