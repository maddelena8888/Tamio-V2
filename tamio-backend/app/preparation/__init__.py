# Preparation Module - Stage 2 of V4 Architecture
# Turns detected problems into actionable solutions

from .models import PreparedAction, ActionOption, ActionType, ActionStatus, LinkedAction
from .engine import PreparationEngine
from .context import (
    get_client_context,
    get_vendor_context,
    get_cash_context,
    get_payroll_context,
)
from .risk_scoring import (
    calculate_composite_risk,
    calculate_relationship_risk,
    calculate_operational_risk,
    calculate_financial_cost,
    score_action_option,
    RiskScore,
)
from .message_drafting import (
    draft_collection_email,
    draft_escalation_email,
    draft_vendor_delay_message,
    draft_vendor_payment_confirmation,
    draft_early_payment_request,
    generate_call_talking_points,
    generate_action_summary,
    enhance_with_ai,
    generate_ai_message,
    suggest_tone,
)
from .escalation import (
    EscalationEngine,
    EscalationResult,
    EscalationReason,
    run_escalation_sweep,
)

__all__ = [
    # Models
    "PreparedAction",
    "ActionOption",
    "ActionType",
    "ActionStatus",
    "LinkedAction",
    # Engine
    "PreparationEngine",
    # Escalation
    "EscalationEngine",
    "EscalationResult",
    "EscalationReason",
    "run_escalation_sweep",
    # Context
    "get_client_context",
    "get_vendor_context",
    "get_cash_context",
    "get_payroll_context",
    # Risk Scoring
    "calculate_composite_risk",
    "calculate_relationship_risk",
    "calculate_operational_risk",
    "calculate_financial_cost",
    "score_action_option",
    "RiskScore",
    # Message Drafting
    "draft_collection_email",
    "draft_escalation_email",
    "draft_vendor_delay_message",
    "draft_vendor_payment_confirmation",
    "draft_early_payment_request",
    "generate_call_talking_points",
    "generate_action_summary",
    # AI Enhancement
    "enhance_with_ai",
    "generate_ai_message",
    "suggest_tone",
]
