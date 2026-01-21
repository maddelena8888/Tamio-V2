# Detection Module - V4 Architecture
# Monitors for specific moments when cash problems require action
#
# Components:
# - engine.py: Main DetectionEngine with all 12 detection types
# - scheduler.py: Background job scheduler (APScheduler integration)
# - escalation.py: Alert escalation logic
# - rules.py: Default rule configurations
# - models.py: DetectionRule, DetectionAlert models

from .models import (
    DetectionRule,
    DetectionAlert,
    DetectionType,
    AlertSeverity,
    AlertStatus,
)

# Alias for backwards compatibility with tests and pipeline
DetectedAlert = DetectionAlert
from .engine import DetectionEngine
from .rules import DETECTION_RULES, get_default_rules_for_user
from .scheduler import (
    DetectionScheduler,
    detection_scheduler,
    setup_apscheduler,
    run_detections_after_sync,
)
from .escalation import (
    EscalationEngine,
    check_payroll_cascade,
    check_deadline_cascade,
)

__all__ = [
    # Models
    "DetectionRule",
    "DetectionAlert",
    "DetectedAlert",  # Alias
    "DetectionType",
    "AlertSeverity",
    "AlertStatus",
    # Engine
    "DetectionEngine",
    # Rules
    "DETECTION_RULES",
    "get_default_rules_for_user",
    # Scheduler
    "DetectionScheduler",
    "detection_scheduler",
    "setup_apscheduler",
    "run_detections_after_sync",
    # Escalation
    "EscalationEngine",
    "check_payroll_cascade",
    "check_deadline_cascade",
]
