"""Treasury models: Client, ExpenseBucket, CashAccount, ExchangeRate."""
from sqlalchemy import Column, String, DateTime, Date, Numeric, Boolean, Integer, Text, ForeignKey, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.database import Base
from app.models.base import generate_id


class Client(Base):
    """Client model - Page 2: Cash In (Revenue Sources)."""

    __tablename__ = "clients"

    id = Column(String, primary_key=True, default=lambda: generate_id("client"))
    user_id = Column(String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)

    # Core Info
    name = Column(String, nullable=False)
    client_type = Column(String, nullable=False)  # "retainer" | "project" | "usage" | "mixed"
    currency = Column(String, nullable=False, default="USD")
    status = Column(String, nullable=False, default="active")  # "active" | "paused" | "deleted"

    # Risk Indicators
    payment_behavior = Column(String, nullable=True)  # "on_time" | "delayed" | "unknown"
    churn_risk = Column(String, nullable=True)  # "low" | "medium" | "high"
    scope_risk = Column(String, nullable=True)  # "low" | "medium" | "high"

    # V4 Required Fields
    # Payment pattern: average days late (0 = on time, positive = days late)
    avg_payment_delay_days = Column(Integer, nullable=True, default=0)

    # Relationship type: strategic clients get softer tone, transactional get firmer
    relationship_type = Column(String, nullable=True)  # "strategic" | "transactional" | "managed"

    # Revenue concentration: what % of total revenue does this client represent?
    revenue_percent = Column(Numeric(precision=5, scale=2), nullable=True)  # e.g., 15.50 = 15.5%

    # Unified risk level for detection/preparation decisions
    risk_level = Column(String, nullable=True)  # "low" | "medium" | "high" | "critical"

    # Billing Configuration (JSONB - adapts by client_type)
    billing_config = Column(JSONB, nullable=False, default=dict)

    # ==========================================================================
    # Bi-directional Sync Fields
    # ==========================================================================
    # Data source: where did this record originate?
    source = Column(String, nullable=False, default="manual")  # "manual" | "xero" | "quickbooks"

    # Xero integration
    xero_contact_id = Column(String, nullable=True, unique=True, index=True)  # Xero Contact UUID
    xero_repeating_invoice_id = Column(String, nullable=True)  # For retainer billing

    # QuickBooks integration (future)
    quickbooks_customer_id = Column(String, nullable=True, unique=True, index=True)

    # Sync state
    sync_status = Column(String, nullable=True)  # "synced" | "pending_push" | "pending_pull" | "conflict" | "error"
    last_synced_at = Column(DateTime(timezone=True), nullable=True)
    sync_error = Column(Text, nullable=True)

    # Field-level locking: which fields are controlled by the external system?
    # If source="xero", these fields are read-only in Tamio UI
    locked_fields = Column(JSONB, nullable=False, default=list)  # e.g., ["name", "currency"]

    # Metadata
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    user = relationship("User", back_populates="clients")

    # One-to-Many: Client -> ObligationAgreement
    # Each client can have multiple obligations (retainer, project milestones, usage fees, etc.)
    obligations = relationship(
        "ObligationAgreement",
        back_populates="client",
        cascade="all, delete-orphan",
        foreign_keys="[ObligationAgreement.client_id]"
    )


class ExpenseBucket(Base):
    """Expense Bucket model - Page 3: Cash Out."""

    __tablename__ = "expense_buckets"

    id = Column(String, primary_key=True, default=lambda: generate_id("bucket"))
    user_id = Column(String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)

    # Bucket Info
    name = Column(String, nullable=False)
    category = Column(String, nullable=False)  # "payroll" | "rent" | "contractor" | "software" | "marketing" | "other"
    bucket_type = Column(String, nullable=False)  # "fixed" | "variable"

    # From Form
    monthly_amount = Column(Numeric(precision=15, scale=2), nullable=False)
    currency = Column(String, nullable=False, default="USD")

    # Base currency normalization (for multi-currency forecasting)
    # When expense currency differs from user's base currency, this stores
    # the converted amount for easy aggregation in forecasts
    base_currency_amount = Column(Numeric(precision=15, scale=2), nullable=True)
    exchange_rate_used = Column(Numeric(precision=18, scale=8), nullable=True)
    exchange_rate_date = Column(Date, nullable=True)

    priority = Column(String, nullable=False)  # "high" | "medium" | "low" or "essential" | "important" | "discretionary"
    is_stable = Column(Boolean, nullable=False, default=True)

    # Payment timing
    due_day = Column(Integer, nullable=True, default=15)  # Day of month (1-28)
    frequency = Column(String, nullable=True, default="monthly")  # "monthly" | "weekly" | "quarterly"

    # V4 Required Vendor Fields
    # Payment terms: Net-30, Net-60, Due on receipt, etc.
    payment_terms = Column(String, nullable=True)  # "net_30" | "net_60" | "net_15" | "due_on_receipt" | "custom"
    payment_terms_days = Column(Integer, nullable=True)  # Actual days if custom or computed from term

    # Flexibility level: can we delay payment if cash is tight?
    flexibility_level = Column(String, nullable=True)  # "can_delay" | "negotiable" | "cannot_delay"

    # Criticality: how essential is this vendor/expense?
    criticality = Column(String, nullable=True)  # "critical" | "important" | "flexible"

    # Past delay history: have we delayed payments to this vendor before?
    delay_history = Column(JSONB, nullable=True, default=list)
    # Format: [{"date": "2024-01-15", "days_delayed": 7, "reason": "cash flow"}, ...]

    # Optional metadata
    employee_count = Column(Integer, nullable=True)  # For payroll buckets
    notes = Column(Text, nullable=True)

    # ==========================================================================
    # Bi-directional Sync Fields
    # ==========================================================================
    # Data source: where did this record originate?
    source = Column(String, nullable=False, default="manual")  # "manual" | "xero" | "quickbooks"

    # Xero integration (suppliers/vendors)
    xero_contact_id = Column(String, nullable=True, unique=True, index=True)  # Xero Supplier Contact UUID
    xero_repeating_bill_id = Column(String, nullable=True)  # For recurring bills

    # QuickBooks integration (future)
    quickbooks_vendor_id = Column(String, nullable=True, unique=True, index=True)

    # Sync state
    sync_status = Column(String, nullable=True)  # "synced" | "pending_push" | "pending_pull" | "conflict" | "error"
    last_synced_at = Column(DateTime(timezone=True), nullable=True)
    sync_error = Column(Text, nullable=True)

    # Field-level locking: which fields are controlled by the external system?
    locked_fields = Column(JSONB, nullable=False, default=list)  # e.g., ["name", "monthly_amount"]

    # Metadata
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    user = relationship("User", back_populates="expense_buckets")

    # One-to-Many: ExpenseBucket -> ObligationAgreement
    # Each expense bucket can have multiple obligations
    obligations = relationship(
        "ObligationAgreement",
        back_populates="expense_bucket",
        cascade="all, delete-orphan",
        foreign_keys="[ObligationAgreement.expense_bucket_id]"
    )


class CashAccount(Base):
    """Cash Account model - Page 1: Current Cash Position."""

    __tablename__ = "cash_accounts"

    id = Column(String, primary_key=True, default=lambda: generate_id("acct"))
    user_id = Column(String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    account_name = Column(String, nullable=False)
    balance = Column(Numeric(precision=15, scale=2), nullable=False)
    currency = Column(String, nullable=False, default="USD")
    as_of_date = Column(Date, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    user = relationship("User", back_populates="cash_accounts")
    payment_events = relationship("PaymentEvent", back_populates="account", cascade="all, delete-orphan")


class ExchangeRate(Base):
    """Exchange rate model - stores currency conversion rates."""

    __tablename__ = "exchange_rates"

    id = Column(String, primary_key=True, default=lambda: generate_id("xrate"))
    from_currency = Column(String, nullable=False, index=True)
    to_currency = Column(String, nullable=False, index=True)
    rate = Column(Numeric(precision=18, scale=8), nullable=False)
    effective_date = Column(Date, nullable=False, index=True)
    source = Column(String, nullable=False, default="ecb")
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    __table_args__ = (
        UniqueConstraint('from_currency', 'to_currency', 'effective_date', name='uq_exchange_rate_currency_date'),
    )
