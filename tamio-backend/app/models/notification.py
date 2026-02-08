"""
Notification Models - V4 Architecture

Database models for notification preferences and history.
"""

from enum import Enum
from uuid import uuid4

from sqlalchemy import Column, String, DateTime, Boolean, Integer, ForeignKey
from sqlalchemy import Enum as SQLEnum
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.database import Base


class NotificationType(str, Enum):
    """Types of notifications that can be sent."""
    # Alert notifications
    ALERT_EMERGENCY = "alert_emergency"      # Emergency severity alert created
    ALERT_THIS_WEEK = "alert_this_week"      # This-week severity alert created
    ALERT_ESCALATED = "alert_escalated"      # Alert severity increased

    # Action notifications
    ACTION_READY = "action_ready"            # Action prepared and ready for approval
    ACTION_DEADLINE = "action_deadline"      # Action deadline approaching
    ACTION_EXECUTED = "action_executed"      # Action was executed

    # System notifications
    SYNC_COMPLETED = "sync_completed"        # Xero sync completed
    SYNC_FAILED = "sync_failed"              # Xero sync failed

    # Digest
    DAILY_DIGEST = "daily_digest"            # Daily summary email


class NotificationChannel(str, Enum):
    """Delivery channels for notifications."""
    EMAIL = "email"
    # Future: SMS = "sms", PUSH = "push", SLACK = "slack"


class NotificationPreference(Base):
    """
    User notification preferences.

    Controls which notification types are enabled and their settings.
    Each user has one preference record per notification type.
    """
    __tablename__ = "notification_preferences"

    id = Column(String, primary_key=True, default=lambda: str(uuid4()))
    user_id = Column(String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)

    # What type of notification
    notification_type = Column(SQLEnum(NotificationType), nullable=False)

    # Channel settings
    email_enabled = Column(Boolean, default=True)
    # Future: sms_enabled, push_enabled, slack_enabled

    # Timing preferences
    # For non-emergency: batch into digest (True) or send immediately (False)
    batch_into_digest = Column(Boolean, default=False)

    # Quiet hours (don't send between these hours, in user's timezone)
    quiet_hours_start = Column(Integer, nullable=True)  # 0-23
    quiet_hours_end = Column(Integer, nullable=True)    # 0-23

    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationship
    user = relationship("User", backref="notification_preferences")

    # Unique constraint: one preference per (user, type)
    __table_args__ = (
        {"sqlite_autoincrement": True},
    )


class NotificationLog(Base):
    """
    Log of sent notifications for audit and debugging.
    """
    __tablename__ = "notification_logs"

    id = Column(String, primary_key=True, default=lambda: str(uuid4()))
    user_id = Column(String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)

    # What was sent
    notification_type = Column(SQLEnum(NotificationType), nullable=False)
    channel = Column(SQLEnum(NotificationChannel), nullable=False)

    # Content
    subject = Column(String, nullable=True)
    recipient = Column(String, nullable=False)  # Email address, phone number, etc.

    # Reference to related entity
    alert_id = Column(String, ForeignKey("detection_alerts.id"), nullable=True)
    action_id = Column(String, ForeignKey("prepared_actions.id"), nullable=True)

    # Status
    sent_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    delivered = Column(Boolean, default=True)
    error_message = Column(String, nullable=True)

    # External reference (e.g., email provider message ID)
    external_id = Column(String, nullable=True)

    # Relationships
    user = relationship("User", backref="notification_logs")
    alert = relationship("DetectionAlert", backref="notifications")
    action = relationship("PreparedAction", backref="notifications")
