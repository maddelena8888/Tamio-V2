"""
Execution Models - V4 Architecture

Records of executed actions for audit trail.
Includes V2 automation rules for auto-execution.
"""

from datetime import datetime
from enum import Enum
from uuid import uuid4

from sqlalchemy import Column, String, DateTime, ForeignKey, JSON, Text, Boolean, Float, Enum as SQLEnum
from sqlalchemy.orm import relationship

from app.database import Base


class ExecutionMethod(str, Enum):
    """How the action was executed."""
    MANUAL = "manual"          # User copied content and executed externally
    AUTOMATED = "automated"    # System executed via API (V2)


class AutomationActionType(str, Enum):
    """Action types that can be automated."""
    INVOICE_FOLLOW_UP = "invoice_follow_up"
    PAYMENT_BATCH = "payment_batch"
    VENDOR_DELAY = "vendor_delay"
    STATUTORY_PAYMENT = "statutory_payment"
    PAYROLL = "payroll"  # Always manual - locked
    EXCESS_ALLOCATION = "excess_allocation"


class ExecutionResult(str, Enum):
    """Result of execution."""
    SUCCESS = "success"
    PARTIAL = "partial"        # Partially completed
    FAILED = "failed"
    PENDING = "pending"        # Waiting for confirmation


class ExecutionRecord(Base):
    """
    Record of an executed action.

    Created when user marks an action as executed (V1)
    or when system auto-executes (V2).
    """
    __tablename__ = "execution_records"

    id = Column(String, primary_key=True, default=lambda: str(uuid4()))
    user_id = Column(String, ForeignKey("users.id"), nullable=False)
    action_id = Column(String, ForeignKey("prepared_actions.id"), nullable=False)
    option_id = Column(String, ForeignKey("action_options.id"), nullable=True)

    # Execution details
    method = Column(SQLEnum(ExecutionMethod), nullable=False, default=ExecutionMethod.MANUAL)
    result = Column(SQLEnum(ExecutionResult), nullable=False, default=ExecutionResult.PENDING)

    # What was actually executed (may differ from prepared content if edited)
    executed_content = Column(JSON, nullable=False, default=dict)

    # External references
    external_reference = Column(String, nullable=True)  # e.g., email message ID, bank reference
    external_system = Column(String, nullable=True)     # e.g., "gmail", "xero", "bank"

    # Timing
    executed_at = Column(DateTime, default=datetime.utcnow)
    confirmed_at = Column(DateTime, nullable=True)      # When result was confirmed

    # Notes
    notes = Column(Text, nullable=True)

    # Relationships
    user = relationship("User")
    action = relationship("PreparedAction")
    option = relationship("ActionOption")


class ExecutionAutomationRule(Base):
    """
    V4 Stage 4 V2: User-defined automation rules.

    Defines what actions can be auto-executed by the system
    based on thresholds and conditions.

    Example configurations from V4 brief:
    - Invoice Follow-ups: Auto-send after approval (exclude strategic clients)
    - Payment Batches: Auto-submit if total <$10,000
    - Vendor Delays: Auto-send to "flexible" vendors
    - Tax/Statutory: Always manual (require explicit approval)
    - Payroll: Always manual (LOCKED - never available for auto)
    """
    __tablename__ = "execution_automation_rules"

    id = Column(String, primary_key=True, default=lambda: str(uuid4()))
    user_id = Column(String, ForeignKey("users.id"), nullable=False)

    # What type of action does this rule apply to?
    action_type = Column(SQLEnum(AutomationActionType), nullable=False)

    # Is automation enabled for this action type?
    auto_execute = Column(Boolean, nullable=False, default=False)

    # Conditions for auto-execution
    # Maximum amount that can be auto-executed (null = no limit)
    threshold_amount = Column(Float, nullable=True)  # e.g., 10000.00

    # Currency for threshold
    threshold_currency = Column(String, nullable=True, default="USD")

    # Tags/categories to exclude from automation
    # e.g., ["strategic"] for clients, ["critical"] for vendors
    excluded_tags = Column(JSON, nullable=False, default=list)

    # Tags/categories to include (if set, only these are auto-executed)
    included_tags = Column(JSON, nullable=True)

    # Require approval before auto-execution? (for review queue)
    require_approval = Column(Boolean, nullable=False, default=True)

    # Is this rule locked (cannot be changed)? Used for payroll
    is_locked = Column(Boolean, nullable=False, default=False)

    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, onupdate=datetime.utcnow)

    # Relationships
    user = relationship("User")
