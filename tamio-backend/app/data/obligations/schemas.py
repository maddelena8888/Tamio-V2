"""
Pydantic schemas for canonical obligation structure.

These schemas validate the 3-layer obligation architecture:
- ObligationAgreement (WHY): The structural reason for cash-out
- ObligationSchedule (WHEN): The timing of expected outflows
- PaymentEvent (REALITY): Confirmed cash-out from bank
"""
from typing import Optional, List, Dict, Any, Literal
from pydantic import BaseModel, Field
from decimal import Decimal
from datetime import date, datetime


# ============================================
# ObligationAgreement Schemas (Layer 1: WHY)
# ============================================

class ObligationAgreementCreate(BaseModel):
    """Schema for creating a new obligation agreement."""

    user_id: str = Field(..., description="User ID who owns this obligation")

    # Source entity links (One-to-Many: Client/ExpenseBucket -> ObligationAgreement)
    client_id: Optional[str] = Field(
        None,
        description="Link to source Client (for revenue obligations). One Client can have multiple obligations."
    )
    expense_bucket_id: Optional[str] = Field(
        None,
        description="Link to source ExpenseBucket (for expense obligations). One ExpenseBucket can have multiple obligations."
    )

    # What kind of obligation?
    obligation_type: Literal[
        "vendor_bill", "subscription", "payroll", "contractor",
        "loan_payment", "tax_obligation", "lease", "other", "revenue"
    ] = Field(..., description="Type of obligation")

    # Amount structure
    amount_type: Literal["fixed", "variable", "milestone"] = Field(
        ..., description="How amount is determined"
    )
    amount_source: Literal[
        "manual_entry", "xero_sync", "repeating_invoice", "contract_upload"
    ] = Field(..., description="Where amount data came from")

    base_amount: Optional[Decimal] = Field(None, gt=0, description="Base or typical amount")
    variability_rule: Optional[Dict[str, Any]] = Field(
        None, description="For variable obligations, how amount is calculated"
    )

    currency: str = Field("USD", description="Currency code (ISO 4217)")

    # Timing
    frequency: Optional[Literal[
        "one_time", "weekly", "bi_weekly", "monthly", "quarterly", "annually"
    ]] = Field(None, description="How often obligation recurs")

    start_date: date = Field(..., description="When obligation starts")
    end_date: Optional[date] = Field(None, description="When obligation ends (null = ongoing)")

    # Categorization
    category: Literal[
        "payroll", "rent", "contractors", "software", "marketing", "other"
    ] = Field(..., description="Expense category")

    # Links
    account_id: Optional[str] = Field(None, description="Cash account for payments")

    # Confidence
    confidence: Literal["high", "medium", "low"] = Field(
        "high", description="Confidence in this obligation"
    )

    # Metadata
    vendor_name: Optional[str] = Field(None, description="Vendor/payee name")
    notes: Optional[str] = Field(None, description="Additional notes")

    # Xero integration
    xero_contact_id: Optional[str] = None
    xero_invoice_id: Optional[str] = None
    xero_repeating_invoice_id: Optional[str] = None


class ObligationAgreementUpdate(BaseModel):
    """Schema for updating an existing obligation agreement."""

    obligation_type: Optional[Literal[
        "vendor_bill", "subscription", "payroll", "contractor",
        "loan_payment", "tax_obligation", "lease", "other"
    ]] = None

    amount_type: Optional[Literal["fixed", "variable", "milestone"]] = None
    base_amount: Optional[Decimal] = Field(None, gt=0)
    variability_rule: Optional[Dict[str, Any]] = None
    currency: Optional[str] = None

    frequency: Optional[Literal[
        "one_time", "weekly", "bi_weekly", "monthly", "quarterly", "annually"
    ]] = None

    start_date: Optional[date] = None
    end_date: Optional[date] = None

    category: Optional[Literal[
        "payroll", "rent", "contractors", "software", "marketing", "other"
    ]] = None

    account_id: Optional[str] = None
    confidence: Optional[Literal["high", "medium", "low"]] = None

    vendor_name: Optional[str] = None
    notes: Optional[str] = None


class ObligationAgreementResponse(BaseModel):
    """Schema for obligation agreement responses."""

    id: str
    user_id: str

    # Source entity links
    client_id: Optional[str] = None
    expense_bucket_id: Optional[str] = None

    obligation_type: str
    amount_type: str
    amount_source: str
    base_amount: Optional[Decimal]
    variability_rule: Optional[Dict[str, Any]]
    currency: str
    frequency: Optional[str]
    start_date: date
    end_date: Optional[date]
    category: str
    account_id: Optional[str]
    confidence: str
    vendor_name: Optional[str]
    notes: Optional[str]
    created_at: datetime
    updated_at: Optional[datetime]

    xero_contact_id: Optional[str]
    xero_invoice_id: Optional[str]
    xero_repeating_invoice_id: Optional[str]

    class Config:
        from_attributes = True


# ============================================
# ObligationSchedule Schemas (Layer 2: WHEN)
# ============================================

class ObligationScheduleCreate(BaseModel):
    """Schema for creating a scheduled payment."""

    obligation_id: str = Field(..., description="Parent obligation agreement")
    due_date: date = Field(..., description="When payment is due")

    period_start: Optional[date] = Field(None, description="Start of period this payment covers")
    period_end: Optional[date] = Field(None, description="End of period this payment covers")

    estimated_amount: Decimal = Field(..., gt=0, description="Expected payment amount")

    estimate_source: Literal[
        "fixed_agreement", "historical_average", "manual_estimate", "xero_invoice"
    ] = Field(..., description="How estimate was determined")

    confidence: Literal["high", "medium", "low"] = Field(
        "medium", description="Confidence in estimate"
    )

    notes: Optional[str] = Field(None, description="Additional notes")


class ObligationScheduleUpdate(BaseModel):
    """Schema for updating a scheduled payment."""

    due_date: Optional[date] = None
    period_start: Optional[date] = None
    period_end: Optional[date] = None
    estimated_amount: Optional[Decimal] = Field(None, gt=0)
    estimate_source: Optional[Literal[
        "fixed_agreement", "historical_average", "manual_estimate", "xero_invoice"
    ]] = None
    confidence: Optional[Literal["high", "medium", "low"]] = None
    status: Optional[Literal["scheduled", "due", "paid", "overdue", "cancelled"]] = None
    notes: Optional[str] = None


class ObligationScheduleResponse(BaseModel):
    """Schema for obligation schedule responses."""

    id: str
    obligation_id: str
    due_date: date
    period_start: Optional[date]
    period_end: Optional[date]
    estimated_amount: Decimal
    estimate_source: str
    confidence: str
    status: str
    notes: Optional[str]
    created_at: datetime
    updated_at: Optional[datetime]

    class Config:
        from_attributes = True


# ============================================
# PaymentEvent Schemas (Layer 3: REALITY)
# ============================================

class PaymentEventCreate(BaseModel):
    """Schema for recording an actual payment."""

    user_id: str = Field(..., description="User ID who made payment")

    # Links to obligation structure
    obligation_id: Optional[str] = Field(None, description="Link to obligation agreement")
    schedule_id: Optional[str] = Field(None, description="Link to specific schedule entry")

    # Payment details
    amount: Decimal = Field(..., gt=0, description="Actual payment amount")
    currency: str = Field("USD", description="Currency code")
    payment_date: date = Field(..., description="Date payment was made")

    account_id: Optional[str] = Field(None, description="Account payment came from")

    # Status
    status: Literal["pending", "completed", "failed", "reversed"] = Field(
        "completed", description="Payment status"
    )

    # Source
    source: Literal[
        "manual_entry", "xero_sync", "bank_feed", "csv_import"
    ] = Field(..., description="Where payment data came from")

    # Metadata
    vendor_name: Optional[str] = Field(None, description="Vendor/payee name")
    payment_method: Optional[str] = Field(None, description="Payment method (bank_transfer, card, etc.)")
    reference: Optional[str] = Field(None, description="Invoice number, transaction ID, etc.")
    notes: Optional[str] = Field(None, description="Additional notes")

    # Xero integration
    xero_payment_id: Optional[str] = None
    xero_bank_transaction_id: Optional[str] = None


class PaymentEventUpdate(BaseModel):
    """Schema for updating a payment event."""

    obligation_id: Optional[str] = None
    schedule_id: Optional[str] = None
    amount: Optional[Decimal] = Field(None, gt=0)
    currency: Optional[str] = None
    payment_date: Optional[date] = None
    account_id: Optional[str] = None
    status: Optional[Literal["pending", "completed", "failed", "reversed"]] = None
    is_reconciled: Optional[bool] = None
    vendor_name: Optional[str] = None
    payment_method: Optional[str] = None
    reference: Optional[str] = None
    notes: Optional[str] = None


class PaymentEventResponse(BaseModel):
    """Schema for payment event responses."""

    id: str
    user_id: str
    obligation_id: Optional[str]
    schedule_id: Optional[str]
    amount: Decimal
    currency: str
    payment_date: date
    account_id: Optional[str]
    status: str
    source: str
    is_reconciled: bool
    reconciled_at: Optional[datetime]
    vendor_name: Optional[str]
    payment_method: Optional[str]
    reference: Optional[str]
    notes: Optional[str]
    created_at: datetime
    updated_at: Optional[datetime]

    xero_payment_id: Optional[str]
    xero_bank_transaction_id: Optional[str]

    class Config:
        from_attributes = True


# ============================================
# Combined Response Schemas
# ============================================

class ObligationWithSchedules(ObligationAgreementResponse):
    """Obligation agreement with its payment schedules."""
    schedules: List[ObligationScheduleResponse] = []


class ObligationWithPayments(ObligationAgreementResponse):
    """Obligation agreement with actual payment events."""
    payment_events: List[PaymentEventResponse] = []


class ObligationFull(ObligationAgreementResponse):
    """Full obligation view with schedules and payments."""
    schedules: List[ObligationScheduleResponse] = []
    payment_events: List[PaymentEventResponse] = []
