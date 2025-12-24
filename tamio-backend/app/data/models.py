"""Database models for Tamio manual data entry system."""
from sqlalchemy import Column, String, DateTime, Date, Numeric, Boolean, Integer, ForeignKey, Index, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.database import Base
import secrets


def generate_id(prefix: str) -> str:
    """Generate a unique ID with a prefix."""
    return f"{prefix}_{secrets.token_hex(6)}"


class User(Base):
    """User model - represents an individual using Tamio."""

    __tablename__ = "users"

    id = Column(String, primary_key=True, default=lambda: generate_id("user"))
    email = Column(String, unique=True, nullable=False, index=True)
    base_currency = Column(String, nullable=False, default="USD")
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    # Relationships
    cash_accounts = relationship("CashAccount", back_populates="user", cascade="all, delete-orphan")
    clients = relationship("Client", back_populates="user", cascade="all, delete-orphan")
    expense_buckets = relationship("ExpenseBucket", back_populates="user", cascade="all, delete-orphan")
    cash_events = relationship("CashEvent", back_populates="user", cascade="all, delete-orphan")


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

    # Billing Configuration (JSONB - adapts by client_type)
    billing_config = Column(JSONB, nullable=False, default=dict)

    # Metadata
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    user = relationship("User", back_populates="clients")
    cash_events = relationship("CashEvent", back_populates="client", cascade="all, delete-orphan")


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

    # Metadata
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    user = relationship("User", back_populates="expense_buckets")
    cash_events = relationship("CashEvent", back_populates="expense_bucket", cascade="all, delete-orphan")


class CashEvent(Base):
    """Cash Event model - Generated from Clients & Buckets."""

    __tablename__ = "cash_events"

    id = Column(String, primary_key=True, default=lambda: generate_id("evt"))
    user_id = Column(String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)

    # Core Fields
    date = Column(Date, nullable=False, index=True)
    week_number = Column(Integer, nullable=False, default=0)
    amount = Column(Numeric(precision=15, scale=2), nullable=False)
    direction = Column(String, nullable=False)  # "in" | "out"

    # Classification
    event_type = Column(String, nullable=False)  # "expected_revenue" | "expected_expense"
    category = Column(String, nullable=True)

    # Relationships
    client_id = Column(String, ForeignKey("clients.id", ondelete="CASCADE"), nullable=True, index=True)
    bucket_id = Column(String, ForeignKey("expense_buckets.id", ondelete="CASCADE"), nullable=True, index=True)

    # Confidence
    confidence = Column(String, nullable=False, default="high")  # "high" | "medium" | "low"
    confidence_reason = Column(String, nullable=True)

    # Recurrence
    is_recurring = Column(Boolean, nullable=False, default=False)
    recurrence_pattern = Column(String, nullable=True)  # "weekly" | "monthly" | "quarterly"

    # Metadata
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    user = relationship("User", back_populates="cash_events")
    client = relationship("Client", back_populates="cash_events")
    expense_bucket = relationship("ExpenseBucket", back_populates="cash_events")

    # Indexes
    __table_args__ = (
        Index("ix_cash_events_user_date", "user_id", "date"),
        Index("ix_cash_events_client_id", "client_id"),
        Index("ix_cash_events_bucket_id", "bucket_id"),
    )
