"""TAMI models - re-exports from consolidated models package.

DEPRECATED: Import from app.models instead.
"""
from app.models.tami import (
    ConversationSession,
    ConversationMessage,
    UserActivityType,
    UserActivity,
)

__all__ = [
    "ConversationSession",
    "ConversationMessage",
    "UserActivityType",
    "UserActivity",
]
