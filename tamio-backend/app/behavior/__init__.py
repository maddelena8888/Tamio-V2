"""
Behavior Analysis Module

This module implements the behavior model layer of the data flow:
- Behavior metrics calculation and storage
- Trigger system for threshold monitoring
- Scenario generation from behavior patterns
- TAMI integration for action orchestration

Data Flow:
→ Data input (APIs + manual)
→ Canonical mapping (normalized transactions + entities + obligations)
→ Live forecast (probabilistic cash curve)
→ Behavior model (this module - learns how your business actually behaves)
→ Scenario analysis (auto-suggested + user-driven)
→ TAMI action orchestration (recommend → draft → execute with approvals)
"""

from app.behavior.models import (
    BehaviorMetric,
    MetricType,
    MetricTrend,
    BehaviorTrigger,
    TriggerStatus,
    TriggeredScenario,
)
from app.behavior.engine import (
    calculate_client_behavior_metrics,
    calculate_expense_behavior_metrics,
    calculate_cash_discipline_metrics,
    calculate_all_behavior_metrics,
)
from app.behavior.triggers import (
    evaluate_triggers,
    get_active_triggers,
)
from app.behavior.generator import (
    generate_scenarios_from_triggers,
)

__all__ = [
    # Models
    "BehaviorMetric",
    "MetricType",
    "MetricTrend",
    "BehaviorTrigger",
    "TriggerStatus",
    "TriggeredScenario",
    # Engine
    "calculate_client_behavior_metrics",
    "calculate_expense_behavior_metrics",
    "calculate_cash_discipline_metrics",
    "calculate_all_behavior_metrics",
    # Triggers
    "evaluate_triggers",
    "get_active_triggers",
    # Generator
    "generate_scenarios_from_triggers",
]
