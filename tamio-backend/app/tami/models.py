"""TAMI Database Models - Conversation persistence and user activity tracking."""
from sqlalchemy import Column, String, DateTime, Text, Boolean, Integer, ForeignKey, Enum as SQLEnum
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from sqlalchemy.dialects.postgresql import JSONB
from enum import Enum

from app.database import Base
from app.data.base import generate_id


class ConversationSession(Base):
    """
    A TAMI conversation session.

    Each session represents a continuous conversation with the user.
    Sessions can be resumed and provide context for TAMI's responses.
    """
    __tablename__ = "tami_conversation_sessions"

    id = Column(String, primary_key=True, default=lambda: generate_id("conv"))
    user_id = Column(String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)

    # Session metadata
    title = Column(String, nullable=True)  # Auto-generated or user-defined title
    started_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    last_message_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)

    # Context snapshot at session start (for reference)
    initial_context_snapshot = Column(JSONB, nullable=True)

    # Relationships
    messages = relationship("ConversationMessage", back_populates="session", cascade="all, delete-orphan")


class ConversationMessage(Base):
    """
    A single message in a TAMI conversation.

    Stores both user messages and TAMI responses with metadata.
    """
    __tablename__ = "tami_conversation_messages"

    id = Column(String, primary_key=True, default=lambda: generate_id("msg"))
    session_id = Column(String, ForeignKey("tami_conversation_sessions.id", ondelete="CASCADE"), nullable=False, index=True)

    # Message content
    role = Column(String, nullable=False)  # 'user', 'assistant', 'system'
    content = Column(Text, nullable=False)

    # TAMI-specific metadata (for assistant messages)
    mode = Column(String, nullable=True)  # TAMIMode value
    ui_hints = Column(JSONB, nullable=True)  # UI hints from response
    tool_calls = Column(JSONB, nullable=True)  # Any tools called

    # Timing
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    # Optional: detected intent for user messages
    detected_intent = Column(String, nullable=True)

    # Relationships
    session = relationship("ConversationSession", back_populates="messages")


class UserActivityType(str, Enum):
    """Types of user activities we track for TAMI context."""
    # Navigation/View activities
    VIEW_DASHBOARD = "view_dashboard"
    VIEW_FORECAST = "view_forecast"
    VIEW_SCENARIOS = "view_scenarios"
    VIEW_CLIENTS = "view_clients"
    VIEW_EXPENSES = "view_expenses"

    # Scenario activities
    CREATE_SCENARIO = "create_scenario"
    EDIT_SCENARIO = "edit_scenario"
    CONFIRM_SCENARIO = "confirm_scenario"
    DISCARD_SCENARIO = "discard_scenario"

    # Data modification activities
    ADD_CLIENT = "add_client"
    EDIT_CLIENT = "edit_client"
    DELETE_CLIENT = "delete_client"
    ADD_EXPENSE = "add_expense"
    EDIT_EXPENSE = "edit_expense"
    DELETE_EXPENSE = "delete_expense"

    # Cash/Balance activities
    UPDATE_CASH_BALANCE = "update_cash_balance"
    ADD_CASH_ACCOUNT = "add_cash_account"

    # Xero activities
    XERO_CONNECT = "xero_connect"
    XERO_SYNC = "xero_sync"

    # TAMI activities
    TAMI_CHAT = "tami_chat"
    TAMI_USE_SUGGESTION = "tami_use_suggestion"

    # Onboarding
    COMPLETE_ONBOARDING = "complete_onboarding"


class UserActivity(Base):
    """
    Tracks user activities for TAMI behavioral context.

    This helps TAMI understand what the user has been doing recently
    and provide more relevant responses.
    """
    __tablename__ = "tami_user_activities"

    id = Column(String, primary_key=True, default=lambda: generate_id("act"))
    user_id = Column(String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)

    # Activity details
    activity_type = Column(String, nullable=False, index=True)

    # Additional context (depends on activity type)
    # e.g., {"client_id": "...", "client_name": "..."} for client activities
    # e.g., {"scenario_id": "...", "scenario_type": "..."} for scenario activities
    context = Column(JSONB, nullable=True)

    # Reference to related entity (if applicable)
    entity_type = Column(String, nullable=True)  # 'client', 'expense', 'scenario', etc.
    entity_id = Column(String, nullable=True)

    # Timing
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False, index=True)

    # Session reference (if activity happened during a TAMI conversation)
    conversation_session_id = Column(String, ForeignKey("tami_conversation_sessions.id", ondelete="SET NULL"), nullable=True)
