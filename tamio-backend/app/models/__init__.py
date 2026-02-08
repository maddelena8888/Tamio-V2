"""
Consolidated models package.

IMPORTANT: Explicit imports only - no wildcards to prevent circular imports.
Use string-based forward references in relationships: relationship("Client", ...)
"""

# Base utilities
from app.models.base import generate_id

# User model
from app.models.user import User

# Treasury models (Client, Expense, CashAccount, ExchangeRate)
from app.models.treasury import Client, ExpenseBucket, CashAccount, ExchangeRate

# Obligation models
from app.models.obligation import ObligationAgreement, ObligationSchedule, PaymentEvent

# Detection models
from app.models.detection import (
    DetectionType,
    AlertSeverity,
    AlertStatus,
    DetectionRule,
    DetectionAlert,
)

# Action models
from app.models.action import (
    ActionType,
    ActionStatus,
    RiskLevel,
    PreparedAction,
    ActionOption,
    LinkedAction,
)

# Execution models
from app.models.execution import (
    ExecutionMethod,
    AutomationActionType,
    ExecutionResult,
    ExecutionRecord,
    ExecutionAutomationRule,
)

# Notification models
from app.models.notification import (
    NotificationType,
    NotificationChannel,
    NotificationPreference,
    NotificationLog,
)

# Xero models
from app.models.xero import XeroConnection, OAuthState, XeroSyncLog

# TAMI models
from app.models.tami import (
    ConversationSession,
    ConversationMessage,
    UserActivityType,
    UserActivity,
)

# Audit models
from app.models.audit import AuditLog

# Scenario models
from app.models.scenario import (
    RuleType,
    RuleSeverity,
    ScenarioType,
    ScenarioStatus,
    FinancialRule,
    Scenario,
    ScenarioEvent,
    RuleEvaluation,
    ScenarioForecast,
)

# User configuration
from app.models.user_config import SafetyMode, UserConfiguration


__all__ = [
    # Utilities
    "generate_id",
    # User
    "User",
    # Treasury
    "Client",
    "ExpenseBucket",
    "CashAccount",
    "ExchangeRate",
    # Obligation
    "ObligationAgreement",
    "ObligationSchedule",
    "PaymentEvent",
    # Detection
    "DetectionType",
    "AlertSeverity",
    "AlertStatus",
    "DetectionRule",
    "DetectionAlert",
    # Action
    "ActionType",
    "ActionStatus",
    "RiskLevel",
    "PreparedAction",
    "ActionOption",
    "LinkedAction",
    # Execution
    "ExecutionMethod",
    "AutomationActionType",
    "ExecutionResult",
    "ExecutionRecord",
    "ExecutionAutomationRule",
    # Notification
    "NotificationType",
    "NotificationChannel",
    "NotificationPreference",
    "NotificationLog",
    # Xero
    "XeroConnection",
    "OAuthState",
    "XeroSyncLog",
    # TAMI
    "ConversationSession",
    "ConversationMessage",
    "UserActivityType",
    "UserActivity",
    # Audit
    "AuditLog",
    # Scenario
    "RuleType",
    "RuleSeverity",
    "ScenarioType",
    "ScenarioStatus",
    "FinancialRule",
    "Scenario",
    "ScenarioEvent",
    "RuleEvaluation",
    "ScenarioForecast",
    # User Configuration
    "SafetyMode",
    "UserConfiguration",
]
