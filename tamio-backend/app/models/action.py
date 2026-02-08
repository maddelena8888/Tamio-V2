"""
Action Models - V4 Architecture

PreparedAction represents work that has been prepared by agents
and is ready for user approval in the Action Queue.
"""

from datetime import datetime
from enum import Enum
from uuid import uuid4

from sqlalchemy import Column, String, DateTime, Float, ForeignKey, JSON, Text, Integer
from sqlalchemy.orm import relationship

from app.database import Base


class ActionType(str, Enum):
    """Types of prepared actions."""
    # Collection actions
    INVOICE_FOLLOW_UP = "invoice_follow_up"
    PAYMENT_REMINDER = "payment_reminder"
    COLLECTION_ESCALATION = "collection_escalation"

    # Payment actions
    PAYMENT_BATCH = "payment_batch"
    VENDOR_DELAY = "vendor_delay"
    PAYMENT_PRIORITIZATION = "payment_prioritization"

    # Payroll actions
    PAYROLL_CONTINGENCY = "payroll_contingency"
    PAYROLL_CONFIRMATION = "payroll_confirmation"

    # Cash management
    EXCESS_CASH_ALLOCATION = "excess_cash_allocation"
    CREDIT_LINE_DRAW = "credit_line_draw"

    # Invoice generation
    INVOICE_GENERATION = "invoice_generation"

    # Statutory
    STATUTORY_PAYMENT = "statutory_payment"


class ActionStatus(str, Enum):
    """Status of prepared actions."""
    PENDING_APPROVAL = "pending_approval"  # Ready for user review
    APPROVED = "approved"                   # User approved, ready to execute
    EDITED = "edited"                       # User modified before approving
    OVERRIDDEN = "overridden"               # User rejected, handling manually
    SKIPPED = "skipped"                     # User deferred
    EXECUTED = "executed"                   # Action completed
    EXPIRED = "expired"                     # Deadline passed without action


class RiskLevel(str, Enum):
    """Risk level for action options."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class PreparedAction(Base):
    """
    A prepared action ready for user approval.

    Created by the Preparation Engine when a DetectionAlert fires.
    Contains one or more options for the user to choose from.
    """
    __tablename__ = "prepared_actions"

    id = Column(String, primary_key=True, default=lambda: str(uuid4()))
    user_id = Column(String, ForeignKey("users.id"), nullable=False)
    alert_id = Column(String, ForeignKey("detection_alerts.id"), nullable=True)

    # Action details
    action_type = Column(String, nullable=False)  # Uses ActionType values as strings
    status = Column(String, nullable=False, default="pending_approval")

    # Problem summary (displayed at top of card)
    problem_summary = Column(String, nullable=False)
    problem_context = Column(Text, nullable=True)  # Key context: $ impact, relationships, dependencies

    # Selected option (after approval)
    selected_option_id = Column(String, nullable=True)

    # Timing
    created_at = Column(DateTime, default=datetime.utcnow)
    deadline = Column(DateTime, nullable=True)  # When action is needed by
    approved_at = Column(DateTime, nullable=True)
    executed_at = Column(DateTime, nullable=True)

    # User notes
    user_notes = Column(Text, nullable=True)  # Notes added by user on skip/override

    # Relationships
    user = relationship("User", back_populates="prepared_actions")
    alert = relationship("DetectionAlert", back_populates="prepared_actions")
    options = relationship("ActionOption", back_populates="action", cascade="all, delete-orphan")


class ActionOption(Base):
    """
    An option within a prepared action.

    Each PreparedAction can have multiple options ranked by risk.
    The first option is typically the recommended one.
    """
    __tablename__ = "action_options"

    id = Column(String, primary_key=True, default=lambda: str(uuid4()))
    action_id = Column(String, ForeignKey("prepared_actions.id"), nullable=False)

    # Option details
    title = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    risk_level = Column(String, nullable=False, default="medium")  # Uses RiskLevel values as strings
    is_recommended = Column(Integer, default=0)  # 1 = recommended option

    # Reasoning (shown to user)
    reasoning = Column(JSON, nullable=False, default=list)
    # e.g., ["Within Net-30 terms (day 22)", "Non-critical service", "Historically flexible"]

    # Risk scoring (composite)
    risk_score = Column(Float, nullable=True)  # 0-100
    relationship_risk = Column(Float, nullable=True)  # 0-1
    operational_risk = Column(Float, nullable=True)   # 0-1
    financial_cost = Column(Float, nullable=True)     # Dollar amount

    # Impact
    cash_impact = Column(Float, nullable=True)  # How this affects cash position
    impact_description = Column(String, nullable=True)  # e.g., "Covers shortage with $3K buffer remaining"

    # Prepared content (ready to use)
    prepared_content = Column(JSON, nullable=False, default=dict)
    # Structure varies by action type:
    # - invoice_follow_up: {"email_subject": "...", "email_body": "...", "recipient": "...", "tone": "soft|professional|firm"}
    # - payment_batch: {"payments": [...], "total": 47000, "csv_data": "..."}
    # - vendor_delay: {"email_subject": "...", "email_body": "...", "new_date": "2024-01-20"}

    # Success probability (for uncertain actions)
    success_probability = Column(Float, nullable=True)  # 0-1

    # Ordering
    display_order = Column(Integer, default=0)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    action = relationship("PreparedAction", back_populates="options")


class LinkedAction(Base):
    """
    Links between related actions.

    When actions are connected (e.g., invoice chase solves payroll shortage),
    they're linked so:
    - They're visually grouped in the UI
    - Approving one can resolve the other
    - System warns if approving both would conflict
    """
    __tablename__ = "linked_actions"

    id = Column(String, primary_key=True, default=lambda: str(uuid4()))
    action_id = Column(String, ForeignKey("prepared_actions.id"), nullable=False)
    linked_action_id = Column(String, ForeignKey("prepared_actions.id"), nullable=False)

    # Link type
    link_type = Column(String, nullable=False)
    # "resolves" - completing action_id resolves linked_action_id
    # "conflicts" - cannot do both
    # "sequence" - linked_action_id should come after action_id

    # Explanation
    link_reason = Column(String, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)
