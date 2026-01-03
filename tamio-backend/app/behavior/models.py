"""
Behavior Models - Phase 1: BehaviorMetric and Trigger Models

These models track learned business behavior patterns and trigger thresholds.
"""
from sqlalchemy import Column, String, DateTime, Boolean, Integer, Enum as SQLEnum, ForeignKey, DECIMAL, Float
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


# =============================================================================
# Enums
# =============================================================================

class MetricType(str, enum.Enum):
    """Types of behavior metrics tracked."""
    # Client Behavior (Predictability + Risk)
    CLIENT_CONCENTRATION = "client_concentration"
    PAYMENT_RELIABILITY = "payment_reliability"
    REVENUE_AT_RISK = "revenue_at_risk"

    # Expense Behavior (Volatility + Controllability)
    EXPENSE_VOLATILITY = "expense_volatility"
    DISCRETIONARY_RATIO = "discretionary_ratio"
    COMMITMENT_COVERAGE = "commitment_coverage"

    # Cash Discipline (Control + Stress)
    BUFFER_INTEGRITY = "buffer_integrity"
    BURN_MOMENTUM = "burn_momentum"
    REACTIVE_DECISION_RATE = "reactive_decision_rate"


class MetricTrend(str, enum.Enum):
    """Trend direction for metrics."""
    IMPROVING = "improving"
    STABLE = "stable"
    WORSENING = "worsening"


class TriggerStatus(str, enum.Enum):
    """Status of a behavior trigger."""
    PENDING = "pending"       # Conditions met but not yet processed
    ACTIVE = "active"         # Scenario generated and awaiting action
    RESOLVED = "resolved"     # User took action or conditions improved
    DISMISSED = "dismissed"   # User dismissed the trigger
    EXPIRED = "expired"       # Time window passed without action


class TriggerSeverity(str, enum.Enum):
    """Severity level of a trigger."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


# =============================================================================
# BehaviorMetric Model
# =============================================================================

class BehaviorMetric(Base):
    """
    Tracks a single behavior metric for a user or entity.

    Metrics are computed periodically and stored for:
    1. Trend analysis over time
    2. Threshold monitoring for triggers
    3. Context building for TAMI
    """
    __tablename__ = "behavior_metrics"

    id = Column(String, primary_key=True, default=lambda: generate_id("bm"))
    user_id = Column(String, ForeignKey("users.id"), nullable=False)

    # Metric identification
    metric_type = Column(String, nullable=False)  # MetricType enum value
    entity_type = Column(String, nullable=True)   # "client", "expense_bucket", None for aggregate
    entity_id = Column(String, nullable=True)     # Specific entity ID if applicable

    # Current values
    current_value = Column(Float, nullable=False)
    previous_value = Column(Float, nullable=True)  # For trend calculation

    # Statistical properties
    mean = Column(Float, nullable=True)           # Rolling mean
    variance = Column(Float, nullable=True)       # Variance/volatility
    std_dev = Column(Float, nullable=True)        # Standard deviation

    # Trend analysis
    trend = Column(String, default="stable")      # MetricTrend enum value
    trend_velocity = Column(Float, default=0.0)   # Rate of change
    trend_confidence = Column(Float, default=0.5) # 0-1 confidence in trend

    # Threshold configuration
    threshold_warning = Column(Float, nullable=True)   # Yellow zone
    threshold_critical = Column(Float, nullable=True)  # Red zone
    is_higher_better = Column(Boolean, default=True)   # Direction of "good"

    # Confidence in the metric
    data_confidence = Column(Float, default=0.5)  # 0-1, how much data backs this

    # Context data (JSONB for flexibility)
    # e.g., {"client_name": "Acme", "payment_history": [...]}
    context_data = Column(JSONB, default=dict)

    # Time tracking
    computed_at = Column(DateTime(timezone=True), server_default=func.now())
    period_start = Column(DateTime(timezone=True), nullable=True)  # Analysis window start
    period_end = Column(DateTime(timezone=True), nullable=True)    # Analysis window end

    # Metadata
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    user = relationship("User", backref="behavior_metrics")

    def is_breached(self) -> bool:
        """Check if metric has breached critical threshold."""
        if self.threshold_critical is None:
            return False
        if self.is_higher_better:
            return self.current_value < self.threshold_critical
        return self.current_value > self.threshold_critical

    def is_warning(self) -> bool:
        """Check if metric is in warning zone."""
        if self.threshold_warning is None:
            return False
        if self.is_higher_better:
            return self.current_value < self.threshold_warning and not self.is_breached()
        return self.current_value > self.threshold_warning and not self.is_breached()


# =============================================================================
# BehaviorTrigger Model
# =============================================================================

class BehaviorTrigger(Base):
    """
    A trigger that fires when behavior metrics cross thresholds.

    Triggers are defined rules that:
    1. Watch specific metrics
    2. Fire when conditions are met
    3. Generate suggested scenarios
    4. Queue recommended actions for TAMI
    """
    __tablename__ = "behavior_triggers"

    id = Column(String, primary_key=True, default=lambda: generate_id("trig"))
    user_id = Column(String, ForeignKey("users.id"), nullable=False)

    # Trigger identification
    name = Column(String, nullable=False)
    description = Column(String, nullable=True)

    # Trigger conditions (JSONB for complex conditions)
    # e.g., {
    #   "metric_type": "payment_reliability",
    #   "operator": "less_than",
    #   "threshold": 70,
    #   "entity_filter": {"concentration_above": 15},
    #   "duration_days": 14
    # }
    conditions = Column(JSONB, nullable=False)

    # Scenario template to generate when triggered
    # e.g., {
    #   "scenario_type": "payment_delay",
    #   "name_template": "{client_name} pays {delay_days} days late for {cycles} cycles",
    #   "parameters": {"delay_days": 21, "cycles": 2}
    # }
    scenario_template = Column(JSONB, nullable=False)

    # Recommended actions when triggered
    # e.g., ["Draft chase sequence", "Adjust forecast confidence", "Recommend buffer hold"]
    recommended_actions = Column(JSONB, default=list)

    # Severity and priority
    severity = Column(String, default="medium")
    priority = Column(Integer, default=50)  # 0-100, higher = more important

    # State
    is_active = Column(Boolean, default=True)
    cooldown_hours = Column(Integer, default=24)  # Hours before re-triggering
    last_triggered_at = Column(DateTime(timezone=True), nullable=True)

    # Metadata
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    user = relationship("User", backref="behavior_triggers")
    triggered_scenarios = relationship("TriggeredScenario", back_populates="trigger", cascade="all, delete-orphan")


# =============================================================================
# TriggeredScenario Model
# =============================================================================

class TriggeredScenario(Base):
    """
    A scenario that was auto-generated from a trigger firing.

    Links behavior triggers to generated scenarios and tracks:
    1. Why the scenario was generated
    2. What actions were recommended
    3. User response and outcomes
    """
    __tablename__ = "triggered_scenarios"

    id = Column(String, primary_key=True, default=lambda: generate_id("ts"))
    trigger_id = Column(String, ForeignKey("behavior_triggers.id"), nullable=False)
    user_id = Column(String, ForeignKey("users.id"), nullable=False)

    # Link to generated scenario (if user ran it)
    scenario_id = Column(String, ForeignKey("scenarios.id"), nullable=True)

    # Trigger context at time of firing
    # Snapshot of metrics and conditions that caused the trigger
    trigger_context = Column(JSONB, nullable=False)

    # Generated scenario details
    scenario_name = Column(String, nullable=False)
    scenario_description = Column(String, nullable=True)
    scenario_type = Column(String, nullable=False)
    scenario_parameters = Column(JSONB, nullable=False)

    # Recommended actions
    recommended_actions = Column(JSONB, default=list)

    # Impact assessment
    severity = Column(String, default="medium")
    estimated_impact = Column(JSONB, default=dict)  # e.g., {"cash_impact": -15000, "weeks_affected": 4}

    # Status tracking
    status = Column(String, default="pending")  # TriggerStatus
    user_response = Column(String, nullable=True)  # "ran_scenario", "dismissed", "deferred"
    response_notes = Column(String, nullable=True)

    # Outcome tracking (if scenario was run)
    outcome = Column(String, nullable=True)  # "confirmed", "modified", "rejected"
    outcome_notes = Column(String, nullable=True)

    # Time tracking
    triggered_at = Column(DateTime(timezone=True), server_default=func.now())
    responded_at = Column(DateTime(timezone=True), nullable=True)
    expires_at = Column(DateTime(timezone=True), nullable=True)  # Auto-expire after X days

    # Metadata
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    trigger = relationship("BehaviorTrigger", back_populates="triggered_scenarios")
    user = relationship("User", backref="triggered_scenarios")
    scenario = relationship("Scenario", backref="trigger_source")


# =============================================================================
# MetricHistory Model (for trend analysis)
# =============================================================================

class MetricHistory(Base):
    """
    Historical snapshots of behavior metrics for trend analysis.

    Stores daily/weekly snapshots to enable:
    1. Long-term trend calculation
    2. Seasonality detection
    3. Anomaly identification
    """
    __tablename__ = "metric_history"

    id = Column(String, primary_key=True, default=lambda: generate_id("mh"))
    user_id = Column(String, ForeignKey("users.id"), nullable=False)

    # Metric identification
    metric_type = Column(String, nullable=False)
    entity_type = Column(String, nullable=True)
    entity_id = Column(String, nullable=True)

    # Values at this point in time
    value = Column(Float, nullable=False)

    # Statistical context
    rolling_mean = Column(Float, nullable=True)
    rolling_std = Column(Float, nullable=True)

    # Time tracking
    recorded_at = Column(DateTime(timezone=True), server_default=func.now())
    period_type = Column(String, default="daily")  # "daily", "weekly", "monthly"

    # Relationships
    user = relationship("User", backref="metric_history")
