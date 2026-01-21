"""
Detection Models - V4 Architecture

Detection rules and alerts for the continuous vigilance layer.
"""

from datetime import datetime
from enum import Enum
from typing import Optional
from uuid import uuid4

from sqlalchemy import Column, String, DateTime, Boolean, Integer, Float, ForeignKey, JSON, Enum as SQLEnum
from sqlalchemy.orm import relationship

from app.database import Base


class DetectionType(str, Enum):
    """Types of detection rules."""
    # Payment tracking
    LATE_PAYMENT = "late_payment"
    UNEXPECTED_REVENUE = "unexpected_revenue"
    UNEXPECTED_EXPENSE = "unexpected_expense"

    # Client/revenue monitoring
    CLIENT_CHURN = "client_churn"
    REVENUE_VARIANCE = "revenue_variance"

    # Obligation monitoring
    PAYMENT_TIMING_CONFLICT = "payment_timing_conflict"
    VENDOR_TERMS_EXPIRING = "vendor_terms_expiring"
    STATUTORY_DEADLINE = "statutory_deadline"

    # Buffer/runway monitoring
    BUFFER_BREACH = "buffer_breach"
    RUNWAY_THRESHOLD = "runway_threshold"

    # Payroll
    PAYROLL_SAFETY = "payroll_safety"
    HEADCOUNT_CHANGE = "headcount_change"


class AlertSeverity(str, Enum):
    """Severity levels for alerts."""
    EMERGENCY = "emergency"      # Must act today
    THIS_WEEK = "this_week"      # Needs attention soon
    UPCOMING = "upcoming"        # Scheduled for future, monitoring only


class AlertStatus(str, Enum):
    """Status of detection alerts."""
    ACTIVE = "active"            # Newly detected, needs attention
    ACKNOWLEDGED = "acknowledged" # User has seen it
    PREPARING = "preparing"       # Action being prepared
    RESOLVED = "resolved"         # Issue resolved
    DISMISSED = "dismissed"       # User dismissed without action


class DetectionRule(Base):
    """
    User-configurable detection rules.

    Each rule defines:
    - What to detect (detection_type)
    - Thresholds for triggering
    - Whether it's enabled
    """
    __tablename__ = "detection_rules"

    id = Column(String, primary_key=True, default=lambda: str(uuid4()))
    user_id = Column(String, ForeignKey("users.id"), nullable=False)

    # Rule configuration
    detection_type = Column(String, nullable=False)  # Use string for simpler DB compatibility
    name = Column(String, nullable=False)  # Display name
    description = Column(String, nullable=True)

    # Thresholds (JSON for flexibility)
    # e.g., {"days_overdue": 7, "min_amount": 1000}
    thresholds = Column(JSON, nullable=False, default=dict)

    # Status
    enabled = Column(Boolean, default=True)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    user = relationship("User", back_populates="detection_rules")
    alerts = relationship("DetectionAlert", back_populates="rule", cascade="all, delete-orphan")


class DetectionAlert(Base):
    """
    Triggered alerts from detection rules.

    When a detection rule fires, it creates an alert that:
    - Describes the problem
    - Has a severity level
    - Links to any prepared actions
    """
    __tablename__ = "detection_alerts"

    id = Column(String, primary_key=True, default=lambda: str(uuid4()))
    user_id = Column(String, ForeignKey("users.id"), nullable=False)
    rule_id = Column(String, ForeignKey("detection_rules.id"), nullable=True)  # Null if system-generated

    # Alert details
    detection_type = Column(String, nullable=False)  # Use string for simpler DB compatibility
    severity = Column(String, nullable=False, default="this_week")
    status = Column(String, nullable=False, default="active")

    # Context (what triggered it)
    title = Column(String, nullable=False)
    description = Column(String, nullable=True)
    context_data = Column(JSON, nullable=False, default=dict)
    # e.g., {"invoice_id": "...", "client_name": "...", "days_overdue": 14, "amount": 25000}

    # Impact assessment
    cash_impact = Column(Float, nullable=True)  # Monetary impact
    urgency_score = Column(Float, nullable=True)  # 0-100 score

    # Timing
    detected_at = Column(DateTime, default=datetime.utcnow)
    deadline = Column(DateTime, nullable=True)  # When action is needed by
    acknowledged_at = Column(DateTime, nullable=True)
    resolved_at = Column(DateTime, nullable=True)

    # Escalation tracking
    escalation_count = Column(Integer, default=0)
    last_escalated_at = Column(DateTime, nullable=True)

    # Relationships
    user = relationship("User", back_populates="detection_alerts")
    rule = relationship("DetectionRule", back_populates="alerts")
    prepared_actions = relationship("PreparedAction", back_populates="alert", cascade="all, delete-orphan")
