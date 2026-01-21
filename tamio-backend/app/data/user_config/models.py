"""
User Configuration Model

Stores user-specific thresholds and settings for the detection and preparation engines.
This is the primary source for detection sensitivity and buffer requirements.
"""
from enum import Enum

from sqlalchemy import Column, String, DateTime, Integer, ForeignKey, Numeric
from sqlalchemy import Enum as SQLEnum
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.database import Base


class SafetyMode(str, Enum):
    """
    Safety mode affects detection sensitivity.

    - conservative: Lower thresholds, earlier warnings, more buffer
    - normal: Default thresholds
    - aggressive: Higher thresholds, later warnings, less buffer
    """
    CONSERVATIVE = "conservative"
    NORMAL = "normal"
    AGGRESSIVE = "aggressive"


class UserConfiguration(Base):
    """
    User-specific configuration for detection and preparation engines.

    This table stores thresholds and preferences that affect:
    1. When detection rules fire (sensitivity)
    2. How alerts are prioritized (buffer requirements)
    3. How preparation agents calculate risk (safety mode)

    Each user has exactly one configuration record (user_id is primary key).
    """
    __tablename__ = "user_configurations"

    # Primary key is user_id (one config per user)
    user_id = Column(
        String,
        ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True,
        nullable=False
    )

    # ==========================================================================
    # Buffer & Runway Settings
    # ==========================================================================

    # Minimum cash buffer for obligations (absolute amount in base currency)
    # Default: $0 - user should configure based on their needs
    obligations_buffer_amount = Column(
        Numeric(precision=15, scale=2),
        nullable=False,
        default=0
    )

    # Runway warning threshold in months
    # Alert fires when runway drops below this many months
    # Default: 6 months
    runway_buffer_months = Column(
        Integer,
        nullable=False,
        default=6
    )

    # ==========================================================================
    # Late Payment Settings
    # ==========================================================================

    # Days after due date to flag an invoice as overdue
    # Default: 7 days
    late_payment_threshold_days = Column(
        Integer,
        nullable=False,
        default=7
    )

    # ==========================================================================
    # Expense Monitoring Settings
    # ==========================================================================

    # Percentage spike to flag as unexpected expense
    # 20 = flag when expense is 20% above 3-month average
    # Default: 20%
    unexpected_expense_threshold_pct = Column(
        Numeric(precision=5, scale=2),
        nullable=False,
        default=20.0
    )

    # ==========================================================================
    # Safety Mode
    # ==========================================================================

    # Affects overall detection sensitivity
    # - conservative: triggers earlier, more warnings
    # - normal: default behavior
    # - aggressive: triggers later, fewer warnings
    safety_mode = Column(
        SQLEnum(SafetyMode, values_callable=lambda obj: [e.value for e in obj]),
        nullable=False,
        default=SafetyMode.NORMAL
    )

    # ==========================================================================
    # Payroll Safety Settings
    # ==========================================================================

    # Days before payroll to check safety
    # Default: 7 days
    payroll_check_days_before = Column(
        Integer,
        nullable=False,
        default=7
    )

    # Minimum buffer to maintain after payroll (as percentage of payroll)
    # 10 = require 10% buffer after payroll is paid
    # Default: 10%
    payroll_buffer_percent = Column(
        Numeric(precision=5, scale=2),
        nullable=False,
        default=10.0
    )

    # ==========================================================================
    # Payment Clustering Settings
    # ==========================================================================

    # Maximum percentage of cash that can be due in one week before alerting
    # 40 = alert if >40% of cash is committed in a single week
    # Default: 40%
    payment_cluster_threshold_pct = Column(
        Numeric(precision=5, scale=2),
        nullable=False,
        default=40.0
    )

    # ==========================================================================
    # Timestamps
    # ==========================================================================
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationship
    user = relationship("User", backref="configuration", uselist=False)

    def __repr__(self):
        return f"<UserConfiguration user_id={self.user_id} safety_mode={self.safety_mode}>"

    def get_threshold_multiplier(self) -> float:
        """
        Get threshold multiplier based on safety mode.

        Conservative: 0.7 (lower thresholds = earlier detection)
        Normal: 1.0
        Aggressive: 1.3 (higher thresholds = later detection)
        """
        if self.safety_mode == SafetyMode.CONSERVATIVE:
            return 0.7
        elif self.safety_mode == SafetyMode.AGGRESSIVE:
            return 1.3
        return 1.0
