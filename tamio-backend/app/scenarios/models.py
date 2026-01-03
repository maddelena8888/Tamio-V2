"""Scenario Analysis Models - Control Engine."""
from sqlalchemy import Column, String, DateTime, Boolean, Integer, Enum as SQLEnum, ForeignKey, DECIMAL
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from datetime import datetime
import secrets
import enum

from app.database import Base


def generate_id(prefix: str) -> str:
    """Generate a unique ID with a prefix."""
    return f"{prefix}_{secrets.token_hex(6)}"


class RuleType(str, enum.Enum):
    """Financial rule types."""
    MINIMUM_CASH_BUFFER = "minimum_cash_buffer"


class RuleSeverity(str, enum.Enum):
    """Rule breach severity levels."""
    GREEN = "green"  # Rules satisfied
    AMBER = "amber"  # Approaching breach
    RED = "red"      # Breach occurred


class ScenarioType(str, enum.Enum):
    """Scenario types for what-if modeling."""
    # Cash In scenarios
    PAYMENT_DELAY = "payment_delay"
    PAYMENT_DELAY_IN = "payment_delay_in"  # Alias for frontend compatibility
    CLIENT_LOSS = "client_loss"
    CLIENT_GAIN = "client_gain"
    CLIENT_CHANGE = "client_change"

    # Cash Out scenarios
    HIRING = "hiring"
    FIRING = "firing"
    CONTRACTOR_GAIN = "contractor_gain"
    CONTRACTOR_LOSS = "contractor_loss"
    INCREASED_EXPENSE = "increased_expense"
    DECREASED_EXPENSE = "decreased_expense"
    PAYMENT_DELAY_OUT = "payment_delay_out"


class ScenarioStatus(str, enum.Enum):
    """Scenario lifecycle status."""
    DRAFT = "draft"              # Being built
    ACTIVE = "active"            # Ready for evaluation
    SAVED = "saved"              # Saved for future reference
    CONFIRMED = "confirmed"      # Committed to reality
    DISCARDED = "discarded"      # Rejected/archived


class FinancialRule(Base):
    """Financial safety rules that evaluate forecast health."""
    __tablename__ = "financial_rules"

    id = Column(String, primary_key=True, default=lambda: generate_id("rule"))
    user_id = Column(String, ForeignKey("users.id"), nullable=False)

    # Rule configuration
    rule_type = Column(String, nullable=False)
    name = Column(String, nullable=False)  # e.g., "3-Month Cash Buffer"
    description = Column(String)

    # Threshold configuration (stored as JSONB for flexibility)
    # e.g., {"months": 3} for minimum_cash_buffer
    threshold_config = Column(JSONB, nullable=False)

    # Evaluation settings
    is_active = Column(Boolean, default=True)
    evaluation_scope = Column(String, default="all")  # "all", "next_13_weeks", etc.

    # Metadata
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    user = relationship("User", backref="financial_rules")


class Scenario(Base):
    """A what-if scenario that models potential changes."""
    __tablename__ = "scenarios"

    id = Column(String, primary_key=True, default=lambda: generate_id("scenario"))
    user_id = Column(String, ForeignKey("users.id"), nullable=False)

    # Scenario identification
    name = Column(String, nullable=False)  # User-defined or auto-generated
    description = Column(String)
    scenario_type = Column(String, nullable=False)
    status = Column(String, default="draft")

    # Entry tracking
    entry_path = Column(String)  # "user_defined", "tamio_suggested"
    suggested_reason = Column(String)  # If Tamio-suggested, why?

    # Scope definition (JSONB for flexibility)
    # e.g., {"client_ids": [...], "effective_date": "2025-01-01"}
    scope_config = Column(JSONB, nullable=False)

    # Scenario parameters (type-specific)
    # e.g., {"delay_weeks": 2, "partial_payment_pct": 50}
    parameters = Column(JSONB, nullable=False)

    # Linked scenarios (second-order effects)
    # e.g., [{"scenario_id": "...", "relationship": "caused_by_client_loss"}]
    linked_scenarios = Column(JSONB, default=list)

    # Layer ordering (for stacked scenarios)
    layer_order = Column(Integer, default=0)
    parent_scenario_id = Column(String, ForeignKey("scenarios.id"), nullable=True)

    # Confirmation tracking
    confirmed_at = Column(DateTime(timezone=True))
    confirmed_by = Column(String)  # user_id or "system"

    # Metadata
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    user = relationship("User", backref="scenarios", foreign_keys=[user_id])
    parent_scenario = relationship("Scenario", remote_side=[id], backref="child_scenarios")
    scenario_events = relationship("ScenarioEvent", back_populates="scenario", cascade="all, delete-orphan")
    rule_evaluations = relationship("RuleEvaluation", back_populates="scenario", cascade="all, delete-orphan")


class ScenarioEvent(Base):
    """Cash events created or modified by a scenario."""
    __tablename__ = "scenario_events"

    id = Column(String, primary_key=True, default=lambda: generate_id("scevt"))
    scenario_id = Column(String, ForeignKey("scenarios.id"), nullable=False)

    # Link to original canonical event (if modifying existing)
    original_event_id = Column(String, ForeignKey("cash_events.id"), nullable=True)

    # Event operation type
    operation = Column(String, nullable=False)  # "add", "modify", "delete"

    # Modified event data (full event snapshot)
    event_data = Column(JSONB, nullable=False)

    # Attribution
    layer_attribution = Column(String)  # Which scenario layer caused this
    change_reason = Column(String)  # Human-readable explanation

    # Metadata
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    scenario = relationship("Scenario", back_populates="scenario_events")
    original_event = relationship("CashEvent", foreign_keys=[original_event_id])


class RuleEvaluation(Base):
    """Result of evaluating a financial rule against a forecast."""
    __tablename__ = "rule_evaluations"

    id = Column(String, primary_key=True, default=lambda: generate_id("eval"))
    rule_id = Column(String, ForeignKey("financial_rules.id"), nullable=False)
    scenario_id = Column(String, ForeignKey("scenarios.id"), nullable=True)  # Null = base forecast
    user_id = Column(String, ForeignKey("users.id"), nullable=False)

    # Evaluation results
    severity = Column(String, nullable=False)
    is_breached = Column(Boolean, default=False)

    # Breach details (if applicable)
    first_breach_week = Column(Integer)  # Week number of first breach
    first_breach_date = Column(String)   # ISO date string
    breach_amount = Column(DECIMAL(15, 2))  # How far below threshold

    # Action window
    action_window_weeks = Column(Integer)  # "You have X weeks to act"

    # Detailed results (JSONB)
    # e.g., {"breached_weeks": [5, 6, 7], "buffer_values": {...}}
    evaluation_details = Column(JSONB, default=dict)

    # Metadata
    evaluated_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    rule = relationship("FinancialRule", backref="evaluations")
    scenario = relationship("Scenario", back_populates="rule_evaluations")
    user = relationship("User")


class ScenarioForecast(Base):
    """Computed forecast output for a scenario."""
    __tablename__ = "scenario_forecasts"

    id = Column(String, primary_key=True, default=lambda: generate_id("scfor"))
    scenario_id = Column(String, ForeignKey("scenarios.id"), nullable=False)
    user_id = Column(String, ForeignKey("users.id"), nullable=False)

    # Forecast data
    forecast_data = Column(JSONB, nullable=False)  # Full 13-week forecast

    # Comparison to base
    delta_data = Column(JSONB, nullable=False)  # Week-by-week deltas

    # Summary metrics
    summary = Column(JSONB, default=dict)

    # Metadata
    computed_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    scenario = relationship("Scenario", backref="forecasts")
    user = relationship("User")
