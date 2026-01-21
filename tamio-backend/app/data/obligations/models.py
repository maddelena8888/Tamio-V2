"""Obligation models for the 3-layer expense/obligation architecture."""
from sqlalchemy import Column, String, DateTime, Date, Numeric, Boolean, Text, ForeignKey, Index
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.database import Base
from app.data.base import generate_id


class ObligationAgreement(Base):
    """
    Obligation Agreement - Layer 1: WHY

    Defines the structural reason for committed cash-out.
    This is the "agreement" or "contract" that creates the obligation.
    """

    __tablename__ = "obligation_agreements"

    id = Column(String, primary_key=True, default=lambda: generate_id("obl"))
    user_id = Column(String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)

    # What kind of obligation is this?
    obligation_type = Column(String, nullable=False)
    # Options:
    # - "vendor_bill": One-time or recurring bill from vendor
    # - "subscription": Recurring SaaS/software subscription
    # - "payroll": Employee salary/wages
    # - "contractor": Contractor payment
    # - "loan_payment": Loan repayment
    # - "tax_obligation": Tax payment
    # - "lease": Rent or lease payment
    # - "other": Custom obligation

    # Amount Structure
    amount_type = Column(String, nullable=False)
    # Options:
    # - "fixed": Same amount every period (e.g., $5000/month salary)
    # - "variable": Amount changes (e.g., usage-based, commission)
    # - "milestone": Triggered by delivery/date (projects)

    amount_source = Column(String, nullable=False)
    # Options:
    # - "manual_entry": User entered manually
    # - "xero_sync": Synced from Xero invoice/bill
    # - "repeating_invoice": From Xero repeating invoice
    # - "contract_upload": Extracted from contract document

    base_amount = Column(Numeric(precision=15, scale=2), nullable=True)
    # Base amount (for fixed) or typical amount (for variable)

    variability_rule = Column(JSONB, nullable=True)
    # For variable obligations, defines how amount is calculated
    # Example: {"type": "hourly_rate", "rate": 150, "estimated_hours": 40}
    # Example: {"type": "commission", "rate": 0.10, "base_sales": 50000}

    currency = Column(String, nullable=False, default="USD")

    # Base currency normalization (for multi-currency forecasting)
    # When obligation currency differs from user's base currency, this stores
    # the converted amount for easy aggregation in forecasts
    base_currency_amount = Column(Numeric(precision=15, scale=2), nullable=True)
    exchange_rate_used = Column(Numeric(precision=18, scale=8), nullable=True)
    exchange_rate_date = Column(Date, nullable=True)

    # Timing
    frequency = Column(String, nullable=True)
    # Options: "one_time", "weekly", "bi_weekly", "monthly", "quarterly", "annually"

    start_date = Column(Date, nullable=False)
    end_date = Column(Date, nullable=True)  # Null = ongoing

    # Categorization
    category = Column(String, nullable=False)
    # Options: "payroll", "rent", "contractors", "software", "marketing", "other"

    # Link to cash account where payment is made from
    account_id = Column(String, ForeignKey("cash_accounts.id", ondelete="SET NULL"), nullable=True)

    # Confidence in this obligation
    confidence = Column(String, nullable=False, default="high")
    # Options: "high", "medium", "low"

    # Metadata
    vendor_name = Column(String, nullable=True)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Xero Integration Fields
    xero_contact_id = Column(String, nullable=True)
    xero_invoice_id = Column(String, nullable=True)
    xero_repeating_invoice_id = Column(String, nullable=True)

    # ==========================================================================
    # Source Entity Links (One-to-Many: Client/ExpenseBucket -> ObligationAgreement)
    # ==========================================================================
    # Link to source Client (for revenue obligations)
    # A Client can have multiple ObligationAgreements (retainer, project milestones, etc.)
    client_id = Column(String, ForeignKey("clients.id", ondelete="SET NULL"), nullable=True, index=True)

    # Link to source ExpenseBucket (for expense obligations)
    # An ExpenseBucket can have multiple ObligationAgreements
    expense_bucket_id = Column(String, ForeignKey("expense_buckets.id", ondelete="SET NULL"), nullable=True, index=True)

    # Relationships
    user = relationship("User", back_populates="obligation_agreements")
    account = relationship("CashAccount")
    schedules = relationship("ObligationSchedule", back_populates="obligation", cascade="all, delete-orphan")
    payment_events = relationship("PaymentEvent", back_populates="obligation", cascade="all, delete-orphan")

    # Source entity relationships
    client = relationship("Client", back_populates="obligations")
    expense_bucket = relationship("ExpenseBucket", back_populates="obligations")

    # Indexes
    __table_args__ = (
        Index("ix_obligation_agreements_user_id", "user_id"),
        Index("ix_obligation_agreements_category", "category"),
        Index("ix_obligation_agreements_type", "obligation_type"),
        Index("ix_obligation_agreements_client_id", "client_id"),
        Index("ix_obligation_agreements_expense_bucket_id", "expense_bucket_id"),
    )


class ObligationSchedule(Base):
    """
    Obligation Schedule - Layer 2: WHEN

    Defines the timing of expected cash outflows for an obligation.
    Each schedule entry represents one expected payment.
    """

    __tablename__ = "obligation_schedules"

    id = Column(String, primary_key=True, default=lambda: generate_id("sched"))
    obligation_id = Column(String, ForeignKey("obligation_agreements.id", ondelete="CASCADE"), nullable=False, index=True)

    # When is payment due?
    due_date = Column(Date, nullable=False, index=True)

    # What period does this cover?
    period_start = Column(Date, nullable=True)
    period_end = Column(Date, nullable=True)

    # How much do we expect to pay?
    estimated_amount = Column(Numeric(precision=15, scale=2), nullable=False)

    # Base currency normalization (for multi-currency forecasting)
    base_currency_amount = Column(Numeric(precision=15, scale=2), nullable=True)
    exchange_rate_used = Column(Numeric(precision=18, scale=8), nullable=True)

    # How was estimate determined?
    estimate_source = Column(String, nullable=False)
    # Options:
    # - "fixed_agreement": From fixed agreement (e.g., monthly retainer)
    # - "historical_average": Based on past payments
    # - "manual_estimate": User provided estimate
    # - "xero_invoice": From Xero invoice amount

    # Confidence in this estimate
    confidence = Column(String, nullable=False, default="medium")
    # Options: "high", "medium", "low"

    # Status
    status = Column(String, nullable=False, default="scheduled")
    # Options:
    # - "scheduled": Future payment, not yet due
    # - "due": Payment is due now
    # - "paid": Payment has been made (linked to PaymentEvent)
    # - "overdue": Payment missed due date
    # - "cancelled": Obligation cancelled

    # Metadata
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    obligation = relationship("ObligationAgreement", back_populates="schedules")
    payment_events = relationship("PaymentEvent", back_populates="schedule", cascade="all, delete-orphan")
    cash_events = relationship("CashEvent", back_populates="obligation_schedule")

    # Indexes
    __table_args__ = (
        Index("ix_obligation_schedules_obligation_id", "obligation_id"),
        Index("ix_obligation_schedules_due_date", "due_date"),
        Index("ix_obligation_schedules_status", "status"),
    )


class PaymentEvent(Base):
    """
    Payment Event - Layer 3: REALITY

    Represents actual confirmed cash-out from bank account.
    Links to ObligationSchedule to reconcile expectations vs reality.
    """

    __tablename__ = "payment_events"

    id = Column(String, primary_key=True, default=lambda: generate_id("pay"))
    user_id = Column(String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)

    # Link to what this payment is for
    obligation_id = Column(String, ForeignKey("obligation_agreements.id", ondelete="SET NULL"), nullable=True, index=True)
    schedule_id = Column(String, ForeignKey("obligation_schedules.id", ondelete="SET NULL"), nullable=True, index=True)

    # Payment Details
    amount = Column(Numeric(precision=15, scale=2), nullable=False)
    currency = Column(String, nullable=False, default="USD")
    payment_date = Column(Date, nullable=False, index=True)

    # Which account did payment come from?
    account_id = Column(String, ForeignKey("cash_accounts.id", ondelete="SET NULL"), nullable=True)

    # Payment Status
    status = Column(String, nullable=False, default="completed")
    # Options:
    # - "pending": Initiated but not yet cleared
    # - "completed": Payment cleared
    # - "failed": Payment failed
    # - "reversed": Payment was reversed/refunded

    # Source
    source = Column(String, nullable=False)
    # Options:
    # - "manual_entry": User entered manually
    # - "xero_sync": Synced from Xero bank transaction
    # - "bank_feed": From bank feed integration
    # - "csv_import": Imported from CSV

    # Reconciliation
    is_reconciled = Column(Boolean, nullable=False, default=False)
    reconciled_at = Column(DateTime(timezone=True), nullable=True)

    # V4 Required: Variance tracking (actual vs expected)
    # Positive = overpaid, Negative = underpaid
    variance_vs_expected = Column(Numeric(precision=15, scale=2), nullable=True)

    # Metadata
    vendor_name = Column(String, nullable=True)
    payment_method = Column(String, nullable=True)  # "bank_transfer", "card", "check", etc.
    reference = Column(String, nullable=True)  # Invoice number, transaction ID, etc.
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Xero Integration
    xero_payment_id = Column(String, nullable=True)
    xero_bank_transaction_id = Column(String, nullable=True)

    # Relationships
    user = relationship("User", back_populates="payment_events")
    obligation = relationship("ObligationAgreement", back_populates="payment_events")
    schedule = relationship("ObligationSchedule", back_populates="payment_events")
    account = relationship("CashAccount", back_populates="payment_events")

    # Indexes
    __table_args__ = (
        Index("ix_payment_events_user_id", "user_id"),
        Index("ix_payment_events_payment_date", "payment_date"),
        Index("ix_payment_events_obligation_id", "obligation_id"),
        Index("ix_payment_events_schedule_id", "schedule_id"),
        Index("ix_payment_events_account_id", "account_id"),
    )
