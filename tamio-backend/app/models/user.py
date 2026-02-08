"""User model."""
from sqlalchemy import Column, String, DateTime, Boolean
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.database import Base
from app.models.base import generate_id


class User(Base):
    """User model - represents an individual using Tamio."""

    __tablename__ = "users"

    id = Column(String, primary_key=True, default=lambda: generate_id("user"))
    email = Column(String, unique=True, nullable=False, index=True)
    hashed_password = Column(String, nullable=True)  # Nullable for Xero-only users
    company_name = Column(String, nullable=True)  # Business/company name for display
    has_completed_onboarding = Column(Boolean, nullable=False, default=False)
    base_currency = Column(String, nullable=False, default="USD")
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    # Business profile fields
    industry = Column(String, nullable=True)
    subcategory = Column(String, nullable=True)
    revenue_range = Column(String, nullable=True)
    business_profile_completed_at = Column(DateTime(timezone=True), nullable=True)

    # Password reset fields
    password_reset_token = Column(String, nullable=True, index=True)
    password_reset_expires = Column(DateTime(timezone=True), nullable=True)

    # Demo account flag
    is_demo = Column(Boolean, nullable=False, default=False)

    # Relationships - Core data
    cash_accounts = relationship("CashAccount", back_populates="user", cascade="all, delete-orphan")
    clients = relationship("Client", back_populates="user", cascade="all, delete-orphan")
    expense_buckets = relationship("ExpenseBucket", back_populates="user", cascade="all, delete-orphan")
    obligation_agreements = relationship("ObligationAgreement", back_populates="user", cascade="all, delete-orphan")
    payment_events = relationship("PaymentEvent", back_populates="user", cascade="all, delete-orphan")

    # Relationships - V4 Detection & Action system
    detection_rules = relationship("DetectionRule", back_populates="user", cascade="all, delete-orphan")
    detection_alerts = relationship("DetectionAlert", back_populates="user", cascade="all, delete-orphan")
    prepared_actions = relationship("PreparedAction", back_populates="user", cascade="all, delete-orphan")

    # User configuration (one-to-one relationship via backref in UserConfiguration model)
