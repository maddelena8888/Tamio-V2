"""Expense Bucket model for cash outflows."""
from sqlalchemy import Column, String, DateTime, Numeric, Boolean, Integer, Text, ForeignKey
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.database import Base
from app.data.base import generate_id


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
    priority = Column(String, nullable=False)  # "high" | "medium" | "low" or "essential" | "important" | "discretionary"
    is_stable = Column(Boolean, nullable=False, default=True)

    # Payment timing
    due_day = Column(Integer, nullable=True, default=15)  # Day of month (1-28)
    frequency = Column(String, nullable=True, default="monthly")  # "monthly" | "weekly" | "quarterly"

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
    cash_events = relationship("CashEvent", back_populates="expense_bucket", cascade="all, delete-orphan")
